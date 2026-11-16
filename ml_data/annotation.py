"""Immutable automatic-label outputs and schema/evidence validation; no reviewer workflow."""
from collections import Counter
from pathlib import Path
import re
import shutil
from .common import (csv_rows, digest, file_hash, fresh_folder, read_json,
                     read_lines, require, seal, verify, write_csv, write_json)
from .sampling import FIELDS
from .label_rules import label_pair_row

LABELER_VERSION = "automatic-proxy-labeler-v3-scoped-coverage"
VALID_STATUSES = {"unlabeled", "labeled", "insufficient_evidence"}
VALID_LABELS = {"0", "1", "2"}
PII_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}|(?<!\d)(?:\+?84|0)\d{9,10}(?!\d)")

def validate_labels(pairs_path, labels_path):
    """Verify text-version integrity, rubric statuses and literal evidence quotes."""
    pairs_cols, base_rows = csv_rows(pairs_path)
    label_cols, lab_rows = csv_rows(labels_path)
    require(tuple(pairs_cols) == FIELDS and tuple(label_cols) == FIELDS, "Pair/label CSV schema must match FIELDS")
    require(len(base_rows) == len(lab_rows) and len(base_rows) > 0, "Row count mismatch between pairs and labels")

    require(len({r["pair_id"] for r in base_rows}) == len(base_rows), "Duplicate pair IDs")
    status_counts = Counter()
    relevance_counts = Counter()

    for idx, (base, row) in enumerate(zip(base_rows, lab_rows), 1):
        for key in ("pair_id", "partition", "cv_id", "jd_id", "cv_version", "jd_version", "cv_text", "jd_text"):
            require(base[key] == row[key], f"Immutable pair column '{key}' modified at row {idx} ({base['pair_id']})")
        require(digest(row["cv_text"]) == row["cv_version"], f"cv_version SHA256 mismatch at row {idx}")
        require(digest(row["jd_text"]) == row["jd_version"], f"jd_version SHA256 mismatch at row {idx}")

        status = row["label_status"].strip()
        require(status in VALID_STATUSES, f"Invalid label_status '{status}' at row {idx}")
        status_counts[status] += 1

        rel = row["relevance_0_1_2"].strip()
        cv_ev = row["cv_evidence"].strip()
        jd_ev = row["jd_evidence"].strip()
        rat = row["rationale"].strip()

        if status == "labeled":
            require(rel in VALID_LABELS, f"Labeled row {idx} requires relevance_0_1_2 in {{0,1,2}}")
            require(cv_ev and jd_ev and rat, f"Labeled row {idx} requires non-empty cv_evidence, jd_evidence and rationale")
            require(cv_ev in row["cv_text"], f"cv_evidence is not a literal substring of cv_text at row {idx}")
            require(jd_ev in row["jd_text"], f"jd_evidence is not a literal substring of jd_text at row {idx}")
            require(not PII_PATTERN.search(rat), f"Potential PII detected in rationale at row {idx}")
            relevance_counts[rel] += 1
        elif status in {"insufficient_evidence"}:
            require(rel == "", f"Status '{status}' at row {idx} must leave relevance_0_1_2 empty, not force a numeric label")
            require(rat, f"Status '{status}' at row {idx} requires rationale explaining ambiguity or missing evidence")
            if cv_ev:
                require(cv_ev in row["cv_text"], f"cv_evidence is not a literal substring of cv_text at row {idx}")
            if jd_ev:
                require(jd_ev in row["jd_text"], f"jd_evidence is not a literal substring of jd_text at row {idx}")
        else:
            require(rel == "", f"Unlabeled row {idx} must have empty relevance_0_1_2")

    return dict(
        valid=True,
        total_pairs=len(lab_rows),
        status_counts=dict(status_counts),
        relevance_counts=dict(relevance_counts),
        complete=status_counts.get("labeled", 0) == len(lab_rows),
        verification_scope="schema, immutable text and literal quotes only; not semantic accuracy",
    )


def label_pairs_by_evidence(dataset, pairs_folder, jd_extraction_dir=None, output=None):
    """Deterministically label all pairs in pairs_folder/pairs.csv using the 4 established evidence criteria and validate."""
    dataset = Path(dataset).resolve()
    pairs_folder = Path(pairs_folder).resolve()
    verify(dataset, "dataset")
    manifest = read_json(pairs_folder / "manifest.json")
    artifact_type = manifest["artifact_type"]
    verify(pairs_folder, artifact_type)

    records = read_lines(dataset / "records.jsonl")
    cv_lookup = {}
    jd_lookup = {}
    for r in records:
        if r["kind"] == "cv":
            cv_lookup[r["record_id"]] = r
            cv_lookup[r["external_id"]] = r
        elif r["kind"] == "jd":
            jd_lookup[r["record_id"]] = r
            jd_lookup[r["external_id"]] = r
    jd_receipts = {}
    if jd_extraction_dir:
        verify(jd_extraction_dir, "jd-extraction")
        for item in read_json(Path(jd_extraction_dir) / "jd_extraction_evidence.json"):
            require(item["job_id"] not in jd_receipts, "Duplicate JD evidence ID")
            jd_receipts[item["job_id"]] = item

    pairs_csv = pairs_folder / "pairs.csv"
    cols, base_rows = csv_rows(pairs_csv)
    labeled_rows = []
    for row in base_rows:
        cv_rec = cv_lookup[row["cv_id"]]
        jd_rec = jd_lookup[row["jd_id"]]
        require(cv_rec["normalized_text_sha256"] == row["cv_version"]
                and jd_rec["normalized_text_sha256"] == row["jd_version"], "Pair text belongs to a different document version")
        receipt = jd_receipts.get(jd_rec["external_id"])
        labeled_rows.append(label_pair_row(row, cv_rec, jd_rec, receipt))

    require(output is not None, "Labeled output must be a new directory; preserve original pair snapshot")
    folder = fresh_folder(output, (dataset, pairs_folder))
    write_csv(folder / "pairs.csv", labeled_rows, cols)
    shutil.copyfile(pairs_csv, folder / "source_pairs.csv")
    validation = validate_labels(pairs_csv, folder / "pairs.csv")
    summary = dict(read_json(pairs_folder / "summary.json"), labeler_version=LABELER_VERSION,
                   label_counts=validation["status_counts"], relevance_counts=validation["relevance_counts"],
                   complete=validation["complete"], label_origin="automatic_rule_proxy", human_verified=False)
    write_json(folder / "summary.json", summary)
    write_json(folder / "validation.json", validation)
    seal(folder, "automatic-labels", dict(source_pairs_manifest_sha256=file_hash(pairs_folder / "manifest.json"),
        dataset_manifest_sha256=file_hash(dataset / "manifest.json"), labels=LABELER_VERSION,
        label_origin="automatic_rule_proxy", human_verified=False, semantic_accuracy_established=False))
    return summary
