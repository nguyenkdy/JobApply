"""Blind development calibration and independent-review comparison (standard library only)."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import shutil

from baseline_common import catalog, read_csv, sha256, write_json, write_table
from run_artifacts import read_json, verified_manifest
from run_bm25 import tokenize

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_VERSION = "jobapply-relevance-draft-v0.1"
VERSION = "calibration-tools-v1"
STATIC = ("pair_id", "reviewer_slot", "rubric_version", "cv_version", "job_version", "cv_text", "jd_text")
RESPONSE = ("annotator_id", "annotation_origin", "label_status", "relevance_0_1_2",
            "cv_evidence", "jd_evidence", "rationale", "reviewed_at")
FIELDS = (*STATIC, *RESPONSE)
STATES = {"", "completed", "needs_review", "insufficient_evidence"}
ORIGINS = {"human_independent", "ai_draft"}
FINAL_FIELDS = ("adjudicator_id", "annotation_origin", "final_status", "final_label",
                "cv_evidence", "jd_evidence", "adjudication_rationale", "adjudicated_at")


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare(run_dir, output, seed=20261112, guidelines=None):
    folder, manifest = verified_manifest(run_dir)
    guidelines = guidelines or ROOT / "docs/ml/annotation_guidelines.md"
    require(RUBRIC_VERSION in guidelines.read_text(encoding="utf-8"), "Guideline version missing")
    required = ["inputs/jobs_pilot.csv", "inputs/cvs_synthetic.csv",
                "inputs/jobapply_experience_v2/jd_experience.csv", "inputs/jobapply_experience_v2/cv_experience.csv"]
    require(set(required).issubset(manifest["artifacts"]), "Run lacks calibration source artifacts")
    jobs = catalog(folder / required[0], "job_id", "match_text")
    cvs = sorted(catalog(folder / required[1], "cv_id", "cv_text"), key=lambda r: r["cv_id"])
    # Sampling metadata is never a label. No score/judgment/rationale file is opened here.
    jd_notes = read_csv(folder / required[2])
    cv_notes = read_csv(folder / required[3])
    rng = random.Random(seed)
    selected, used = [], set()
    vocabulary = set("python java django react sql docker kubernetes selenium pytest aws javascript typescript linux".split())
    require(len(cvs) == 6, "This versioned calibration design requires the six-CV development pilot")
    for index, cv in enumerate(cvs):
        months = {r["scope"]: int(r["months"]) for r in cv_notes if r["cv_id"] == cv["cv_id"]}
        skills = set(tokenize(cv["skills_text"])) & vocabulary
        categories = ["same_role_shared_stack", "shared_skill_other_role", "experience_threshold",
                      "information_gap" if index < 3 else "preferred_requirements"]
        for category in categories:
            candidates = []
            for job in sorted(jobs, key=lambda r: r["job_id"]):
                if (cv["cv_id"], job["job_id"]) in used:
                    continue
                shared = skills & set(tokenize(job["match_text"]))
                notes = [r for r in jd_notes if r["job_id"] == job["job_id"] and r["threshold_months"]]
                thresholds = [(r["scope"], int(r["threshold_months"]) + int(r["strictly_greater"])) for r in notes]
                same_role = cv["target_role"] == job["pilot_group"]
                match = {
                    "same_role_shared_stack": same_role and bool(shared),
                    "shared_skill_other_role": not same_role and bool(shared),
                    "experience_threshold": any(scope in months and threshold > months[scope] for scope, threshold in thresholds),
                    "information_gap": not thresholds or any(scope not in months for scope, _ in thresholds),
                    "preferred_requirements": bool(job["preferred_requirements_text"].strip()),
                }[category]
                if match:
                    candidates.append((job, sorted(shared)))
            require(candidates, f"No candidates for {cv['cv_id']}/{category}; inspect design")
            job, shared = rng.choice(candidates)
            used.add((cv["cv_id"], job["job_id"]))
            cv_version, job_version = text_hash(cv["cv_text"]), text_hash(job["match_text"])
            pair_id = "CAL_" + text_hash("|".join((cv["cv_id"], job["job_id"], cv_version, job_version)))[:16]
            selected.append(dict(pair_id=pair_id, cv_id=cv["cv_id"], job_id=job["job_id"],
                                 cv_version=cv_version, job_version=job_version, cv_text=cv["cv_text"], jd_text=job["match_text"],
                                 stratum=category, selection_reason=f"{category}; shared technical terms: {', '.join(shared)}",
                                 eligible_candidate_count=len(candidates)))
    require(len(selected) == 24, "Expected 24 unique calibration pairs")
    output = Path(output)
    require(not output.resolve().is_relative_to(folder), "Calibration output must be outside the immutable run")
    output.mkdir(parents=True, exist_ok=False)
    coordinator = output / "coordinator"
    coordinator.mkdir()
    for slot, offset in (("A", 1), ("B", 2)):
        target = output / ("reviewer_" + slot)
        target.mkdir()
        rows = [dict(pair_id=r["pair_id"], reviewer_slot=slot, rubric_version=RUBRIC_VERSION,
                     cv_version=r["cv_version"], job_version=r["job_version"], cv_text=r["cv_text"], jd_text=r["jd_text"],
                     **{key: "" for key in RESPONSE}) for r in selected]
        random.Random(seed + offset).shuffle(rows)
        write_table(target / "review.csv", rows, FIELDS)
        shutil.copyfile(guidelines, target / "annotation_guidelines.md")
        (target / "START_HERE.txt").write_text(
            f"Reviewer {slot}: read annotation_guidelines.md, then fill a COPY of review.csv.\n"
            "This is development calibration with a draft rubric, not final test or verified gold.\n"
            "Work independently. Do not read coordinator files, AI labels, scores or another reviewer file.\n"
            "Keep every row, text and version unchanged. Empty responses mean not yet reviewed.\n"
            "Use a stable personal annotator ID; A/B are distribution slots, not reviewer identities.\n"
            "Return only your completed CSV to the coordinator. Do not put it in the baseline run.\n",
            encoding="utf-8", newline="\n")
    # Keep reasons and original IDs with coordinator only, not in reviewer packets.
    batch = dict(version=VERSION, rubric_version=RUBRIC_VERSION, rubric_status="draft_awaiting_specialist_approval",
                 scope="development calibration; not final test; no verified labels", seed=seed,
                 reviewer_shuffle_seeds=dict(A=seed + 1, B=seed + 2), source_run_manifest_sha256=sha256(folder / "manifest.json"),
                 input_hashes={name: manifest["artifacts"][name]["sha256"] for name in required},
                 tool_sha256=sha256(Path(__file__)), guidelines_sha256=sha256(guidelines),
                 selection_uses="professional text, pilot sampling groups, draft experience metadata; no relevance/score/rank inputs",
                 pairs=selected)
    write_json(coordinator / "batch_manifest.json", batch)
    write_json(coordinator / "packet_hashes.json", {p.relative_to(output).as_posix(): sha256(p)
               for p in sorted(output.rglob("*")) if p.is_file()})
    return dict(pairs=len(selected), by_stratum=dict(Counter(r["stratum"] for r in selected)), output=str(output))


def load_batch(batch_dir):
    batch_dir = Path(batch_dir)
    receipts = read_json(batch_dir / "coordinator/packet_hashes.json")
    for name, digest in receipts.items():
        path = (batch_dir / name).resolve()
        require(path.is_relative_to(batch_dir.resolve()), "Packet path escapes batch")
        require(sha256(path) == digest, f"Original packet changed: {name}; work on reviewer copies")
    batch = read_json(batch_dir / "coordinator/batch_manifest.json")
    require(batch.get("version") == VERSION and batch.get("rubric_version") == RUBRIC_VERSION, "Unsupported batch/rubric version")
    pairs = {r["pair_id"]: r for r in batch["pairs"]}
    require(len(pairs) == len(batch["pairs"]) and pairs, "Empty or duplicate manifest pairs")
    for row in pairs.values():
        require(text_hash(row["cv_text"]) == row["cv_version"] and text_hash(row["jd_text"]) == row["job_version"],
                "Manifest text version mismatch")
    return batch, pairs


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.utcoffset() is not None, "Timestamp must include timezone")
    except (ValueError, TypeError) as exc:
        raise ValueError("Use an ISO timestamp with timezone, e.g. 2026-11-12T15:00:00+07:00") from exc


def evidence(row, reference, reason_key="rationale"):
    require(row[reason_key].strip(), "A rationale is required")
    for key, text in (("cv_evidence", "cv_text"), ("jd_evidence", "jd_text")):
        require(row[key].strip() and row[key] in reference[text], f"{key} must be a non-empty exact excerpt of {text}")


def validate_reviews(batch_dir, path, slot):
    require(slot in {"A", "B"}, "Reviewer slot must be A or B")
    batch, pairs = load_batch(batch_dir)
    rows = read_csv(path, FIELDS)
    require(list(rows[0]) == list(FIELDS), "Reviewer CSV schema/order differs from template")
    by_id = {}
    for row in rows:
        pid = row["pair_id"]
        require(pid in pairs and pid not in by_id, f"Unknown or duplicate pair ID: {pid}")
        ref = pairs[pid]
        require(row["reviewer_slot"] == slot and row["rubric_version"] == batch["rubric_version"], f"Wrong reviewer/rubric: {pid}")
        require(all(row[k] == ref[k] for k in ("cv_version", "job_version", "cv_text", "jd_text")), f"Text/version changed: {pid}")
        state = row["label_status"]
        require(state in STATES, f"Unknown label status: {pid}")
        if not state:
            require(not any(row[k] for k in RESPONSE), f"Partial response without status: {pid}")
        else:
            require(row["annotation_origin"] in ORIGINS, f"Use human_independent or ai_draft; adjudication uses a separate form: {pid}")
            require(row["annotator_id"].strip() == row["annotator_id"] and row["annotator_id"], f"Missing/padded annotator ID: {pid}")
            grade = row["relevance_0_1_2"]
            require(grade in {"0", "1", "2"} if state == "completed" else grade == "", f"Label/status conflict: {pid}")
            evidence(row, ref)
            timestamp(row["reviewed_at"])
        by_id[pid] = row
    require(set(by_id) == set(pairs), "Missing rows: retain unreviewed pairs with blank responses")
    people = {r["annotator_id"].casefold() for r in rows if r["annotation_origin"] == "human_independent"}
    require(len(people) <= 1, "One independent human reviewer per slot; split mixed submissions")
    counts = Counter(r["label_status"] or "unreviewed" for r in rows)
    summary = dict(total=len(rows), counts={k: counts[k] for k in ("unreviewed", "completed", "needs_review", "insufficient_evidence")},
                   eligible_completed=sum(eligible(r) for r in rows),
                   origins=dict(Counter(r["annotation_origin"] or "unassigned" for r in rows)),
                   note="Structural validation does not verify human identity, expertise, independence or label correctness")
    return by_id, summary


def eligible(row):
    return row["label_status"] == "completed" and row["annotation_origin"] == "human_independent"


def agreement(pairs):
    matrix = [[0] * 3 for _ in range(3)]
    for a, b in pairs:
        require(type(a) is int and type(b) is int and a in (0, 1, 2) and b in (0, 1, 2), "Invalid agreement grade")
        matrix[a][b] += 1
    n = len(pairs)
    observed, expected, kappa, exact = None, None, None, None
    reason = "no_eligible_pairs"
    if n:
        exact = sum(matrix[i][i] for i in range(3)) / n
        rows = [sum(row) for row in matrix]
        cols = [sum(matrix[i][j] for i in range(3)) for j in range(3)]
        observed = sum(((i-j)/2)**2 * matrix[i][j] for i in range(3) for j in range(3)) / n
        expected = sum(((i-j)/2)**2 * rows[i] * cols[j] for i in range(3) for j in range(3)) / n**2
        reason = "zero_expected_disagreement" if math.isclose(expected, 0, abs_tol=1e-15) else None
        if reason is None:
            kappa = 1 - observed / expected
    return dict(eligible_pairs=n, exact_agreement=exact, confusion_matrix=matrix,
                matrix_axes="rows reviewer A, columns reviewer B; labels [0,1,2]",
                weighted_cohen_kappa=kappa, weights="quadratic disagreement: ((a-b)/2)^2",
                observed_weighted_disagreement=observed, expected_weighted_disagreement=expected,
                undefined_reason=reason, warning="Small development calibration; no gold threshold or quality certification")


def queue_fields():
    return ["pair_id", "rubric_version", "cv_version", "job_version", "cv_text", "jd_text", "queue_reason",
            *[f"{slot}_{key}" for slot in ("A", "B") for key in RESPONSE], *FINAL_FIELDS]


def compare_reviews(batch_dir, a_path, b_path, output):
    batch, pairs = load_batch(batch_dir)
    a, a_summary = validate_reviews(batch_dir, a_path, "A")
    b, b_summary = validate_reviews(batch_dir, b_path, "B")
    people = [{r["annotator_id"].casefold() for r in data.values() if r["annotation_origin"] == "human_independent"} for data in (a, b)]
    require(not (people[0] & people[1]), "A/B use the same annotator ID; not independent reviews")
    comparable, queue = [], []
    for pid in sorted(pairs):
        left, right = a[pid], b[pid]
        both = eligible(left) and eligible(right)
        if both:
            comparable.append((int(left["relevance_0_1_2"]), int(right["relevance_0_1_2"])))
            if left["relevance_0_1_2"] == right["relevance_0_1_2"]:
                continue
        reason = "label_disagreement" if both else ("awaiting_reviews" if not left["label_status"] or not right["label_status"] else "unresolved_or_nonindependent")
        ref = pairs[pid]
        queue.append(dict(pair_id=pid, rubric_version=batch["rubric_version"],
                          **{k: ref[k] for k in ("cv_version", "job_version", "cv_text", "jd_text")}, queue_reason=reason,
                          **{f"{slot}_{key}": data[pid][key] for slot, data in (("A", a), ("B", b)) for key in RESPONSE},
                          **{key: "" for key in FINAL_FIELDS}))
    output = Path(output)
    require(not output.resolve().is_relative_to(Path(batch_dir).resolve()), "Comparison output must be outside the immutable batch")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(a_path, output / "reviewer_A.original.csv")
    shutil.copyfile(b_path, output / "reviewer_B.original.csv")
    write_table(output / "adjudication.csv", queue, queue_fields())
    report = dict(scope=batch["scope"], rubric_status=batch["rubric_status"], reviewers=dict(A=a_summary, B=b_summary),
                  agreement=agreement(comparable), queue_counts=dict(Counter(r["queue_reason"] for r in queue)),
                  adjudication_required=len(queue), status_disagreements=sum(a[p]["label_status"] != b[p]["label_status"] for p in pairs),
                  originals={"A": sha256(output / "reviewer_A.original.csv"), "B": sha256(output / "reviewer_B.original.csv")},
                  batch_manifest_sha256=sha256(Path(batch_dir) / "coordinator/batch_manifest.json"),
                  gold_status="not_established; draft rubric; no automatic adjudication")
    write_json(output / "report.json", report)
    write_json(output / "comparison_manifest.json", {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()})
    return report


def read_optional_table(path, fields):
    """An adjudication queue may legitimately contain zero pairs."""
    import csv
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == list(fields), "Adjudication schema/order mismatch")
        rows = list(reader)
        require(all(None not in r and all(v is not None for v in r.values()) for r in rows), "Malformed adjudication record")
        return rows


def validate_adjudication(comparison_dir, path):
    folder = Path(comparison_dir)
    receipts = read_json(folder / "comparison_manifest.json")
    for name, digest in receipts.items():
        target = (folder / name).resolve()
        require(target.is_relative_to(folder.resolve()) and sha256(target) == digest, "Original comparison artifacts changed")
    original = {r["pair_id"]: r for r in read_optional_table(folder / "adjudication.csv", queue_fields())}
    rows = read_optional_table(Path(path), queue_fields())
    seen = set()
    immutable = set(queue_fields()) - set(FINAL_FIELDS)
    for row in rows:
        pid = row["pair_id"]
        require(pid in original and pid not in seen, f"Duplicate/unknown adjudication pair: {pid}")
        seen.add(pid)
        require(all(row[k] == original[pid][k] for k in immutable), f"Original reviewer data changed: {pid}")
        status = row["final_status"]
        require(status in STATES, "Invalid final status")
        if not status:
            require(not any(row[k] for k in FINAL_FIELDS), "Partial adjudication without final status")
            continue
        require(all(row[f"{slot}_annotation_origin"] == "human_independent" and row[f"{slot}_label_status"] for slot in ("A", "B")),
                "Await two human reviews before adjudication; unresolved evidence may remain")
        require(row["annotation_origin"] == "human_adjudicated", "Final decision needs human_adjudicated origin")
        person = row["adjudicator_id"]
        require(person.strip() == person and person and person.casefold() not in {row["A_annotator_id"].casefold(), row["B_annotator_id"].casefold()},
                "Adjudicator must be a named third reviewer")
        require(row["final_label"] in {"0", "1", "2"} if status == "completed" else row["final_label"] == "", "Final label/status conflict")
        evidence(row, original[pid], "adjudication_rationale")
        timestamp(row["adjudicated_at"])
    require(seen == set(original), "Missing adjudication rows")
    return dict(total=len(rows), statuses=dict(Counter(r["final_status"] or "pending" for r in rows)),
                gold_status="not_established; structural validation only", original_reviews_preserved=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--seed", type=int, default=20261112)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--batch-dir", type=Path, required=True)
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--reviewer", choices=["A", "B"], required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--batch-dir", type=Path, required=True)
    compare_parser.add_argument("--a", type=Path, required=True)
    compare_parser.add_argument("--b", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    final_parser = sub.add_parser("validate-adjudication")
    final_parser.add_argument("--comparison-dir", type=Path, required=True)
    final_parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.run_dir, args.output, args.seed)
        elif args.command == "validate":
            _, result = validate_reviews(args.batch_dir, args.input, args.reviewer)
        elif args.command == "compare":
            result = compare_reviews(args.batch_dir, args.a, args.b, args.output)
        else:
            result = validate_adjudication(args.comparison_dir, args.input)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Annotation error: {exc}\n")


if __name__ == "__main__":
    main()
