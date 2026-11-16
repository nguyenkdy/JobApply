"""Export all quality-gated JD candidates without reselection, labels or training."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import shutil

from .common import (ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines,
                     require, seal, verify, write_csv, write_json, write_lines)
from .ingest import ingest
from .jd_integrity import assert_frozen_jd_identity_and_exposure
from .splitting import load_dataset

VERSION = "all-eligible-jd-v1"


def disposition(row):
    if row["decision"] == "quarantine":
        return "quarantine"
    if row["decision"] == "exclude_exact_duplicate":
        return "exclude_exact_duplicate"
    require(row["decision"] == "keep", "Unknown JD quality decision")
    return "development_only" if row["development_only"] else "catalogue_candidate"


def catalogue_views(records, used_ids):
    jobs = sorted((r for r in records if r["kind"] == "jd"), key=lambda r: r["record_id"])
    require(len({r["record_id"] for r in jobs}) == len(jobs), "Duplicate JD record ID")
    require(len({r["external_id"] for r in jobs}) == len(jobs), "Duplicate JD source ID")
    candidates = [r for r in jobs if disposition(r) == "catalogue_candidate"]
    by_id = {r["record_id"]: r for r in candidates}
    require(set(used_ids) <= set(by_id), "Prior benchmark contains an ineligible/unknown JD")
    used_groups = {by_id[r]["group_id"] for r in used_ids}
    dev_groups = {r["group_id"] for r in jobs if r["development_only"]}
    require(not dev_groups & {r["group_id"] for r in candidates}, "Development group leaked into catalogue")
    members = defaultdict(list)
    for row in candidates:
        members[row["group_id"]].append(row["record_id"])
    audit = []
    for row in jobs:
        flags = [f + "_unknown" for f in ("role", "skills", "stack", "experience") if not row[f]]
        exposure = ("completed_benchmark" if row["record_id"] in used_ids else
                    "same_group_as_completed_benchmark" if row["group_id"] in used_groups else
                    "source_development" if row["development_only"] else "not_in_completed_benchmark_groups")
        if len(members[row["group_id"]]) > 1:
            flags.append("multiple_candidate_records_in_group")
        audit.append(dict(record_id=row["record_id"], external_id=row["external_id"], group_id=row["group_id"],
            disposition=disposition(row), quality_decision=row["decision"], quality_reasons=row["decision_reasons"],
            source_exposure=row["exposure"], development_only=row["development_only"],
            benchmark_exposure=exposure, metadata_flags=flags,
            metadata_fields_present=all(bool(row[f]) for f in ("role", "skills", "stack", "experience"))))
    groups = [dict(group_id=g, record_ids=sorted(ids), representative_id=min(ids),
                   completed_benchmark_group=g in used_groups) for g, ids in sorted(members.items()) if ids]
    return candidates, audit, groups


def audit_evidence(source_rows, receipts):
    source = {r["job_id"]: r for r in source_rows}
    require(len(source) == len(source_rows), "Duplicate source JD IDs")
    require(len(receipts) == len(source) and {r["job_id"] for r in receipts} == set(source), "Evidence/source IDs mismatch")
    count = 0
    for receipt in receipts:
        row = source[receipt["job_id"]]
        items = [*receipt["role_evidence"], *receipt["experience_evidence"], *receipt.get("requirement_clauses", [])]
        for field in ("skill_evidence", "stack_evidence", "preferred_skill_evidence"):
            items.extend(receipt[field].values())
        for item in items:
            text = row[item["field"]]
            require(type(item["start"]) is int and type(item["end"]) is int and
                    0 <= item["start"] < item["end"] <= len(text) and text[item["start"]:item["end"]] == item["quote"],
                    "Evidence span does not match source: " + receipt["job_id"])
            count += 1
        require(row["extracted_role"] == receipt["role"] and
                set(filter(None, row["extracted_skills"].split(";"))) == set(receipt["skills"]) and
                set(filter(None, row["extracted_stack"].split(";"))) == set(receipt["stack"]) and
                json.loads(row["extracted_experience_json"]) == receipt["experience"], "Metadata/evidence mismatch")
    return dict(jd_count=len(receipts), literal_spans_verified=count,
                semantic_accuracy_established=False, extraction_rerun=False,
                extractor_versions=sorted({r["extractor_version"] for r in receipts}))


def coverage_plan(candidates, cvs):
    by_role = []
    for role in sorted({r["role"] for r in candidates if r["role"]} | {r["role"] for r in cvs if r["role"]}):
        subset = [r for r in candidates if r["role"] == role]
        by_role.append(dict(role=role, jd_count=len(subset), jd_groups=len({r["group_id"] for r in subset}),
                            existing_cv_count=sum(r["role"] == role for r in cvs),
                            missing={f: sum(not r[f] for r in subset) for f in ("skills", "stack", "experience")}))
    unresolved = sum(not c["role"] or not j["role"] or
                     (c["role"] == j["role"] and (not c["skills"] or not j["skills"])) for c in cvs for j in candidates)
    return dict(by_role=by_role, unknown_role_jds=sum(not j["role"] for j in candidates),
        observed_cv_count=len(cvs), full_grid_pairs=len(cvs)*len(candidates),
        pairs_missing_minimum_proxy_metadata=unresolved,
        pairs_with_minimum_proxy_metadata=len(cvs)*len(candidates)-unresolved,
        interpretation="Workload/metadata forecast only. No pair labels generated; previous CVs are regression data after Step 4.")


def expand_catalogue(preparation, benchmark, output):
    prep, benchmark = Path(preparation).resolve(), Path(benchmark).resolve()
    verify(prep, "pretraining-ready")
    verify(benchmark, "step4-experiment")
    prep_hash, benchmark_hash = file_hash(prep / "manifest.json"), file_hash(benchmark / "manifest.json")
    require(read_json(benchmark / "input_receipt.json")["manifest_sha256"] == prep_hash, "Benchmark belongs to another preparation")
    require(read_json(benchmark / "manifest.json")["test_evaluated"], "Expected a completed historical benchmark")
    protected = read_json(prep / "protected_input_hashes.json")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Original input/pilot changed")
    source_records = read_lines(prep / "dataset/records.jsonl")
    used = read_json(prep / "split/eval_catalogue.json")["record_ids"]
    require(set(used) == {r["record_id"] for r in read_json(benchmark / "documents.json").values() if r["kind"] == "jd"}, "Completed benchmark catalogue differs")
    folder = fresh_folder(output, (prep, benchmark))
    write_json(folder / "policy.json", dict(version=VERSION, purpose="All eligible JD candidates for dataset expansion",
        selection="All keep JD outside source development groups; no role/metadata/quota/seed selection",
        duplicates="Exact exclusions stay excluded; all near-group candidate records retained with group IDs",
        exposure="Completed benchmark IDs and their entire groups remain known; previously evaluated CV groups are regression only",
        evaluation="No fresh final test or CV split; no training, labels or application DB imports"))
    config = deepcopy(read_json(prep / "import_config.json"))
    config["dataset_version"] = VERSION + "-" + prep_hash[:12]
    config["sources"] = [s for s in config["sources"] if s["kind"] == "jd"]
    require(len(config["sources"]) == 1, "Three upstream stages must not be imported as separate sources")
    config["sources"][0]["path"] = str((prep / config["sources"][0]["path"]).resolve())
    config.pop("historical_cv_sources", None)
    config["context_files"] = [c for c in config["context_files"] if c["role"] in
                               {"upstream_stage_not_additional_records", "lineage_quality_selection_evidence", "jd_metadata_evidence"}]
    for item in config["context_files"]:
        item["path"] = str((prep / item["path"]).resolve())
    write_json(folder / "import_config.json", config)
    imported = ingest(folder / "import_config.json", folder / "dataset")
    _, records, _ = load_dataset(folder / "dataset")
    identity = assert_frozen_jd_identity_and_exposure(source_records, records)
    # Also preserve enriched metadata, not just original text/quality/exposure.
    old = {r["record_id"]: r for r in source_records if r["kind"] == "jd"}
    require(all(all(r[f] == old[r["record_id"]][f] for f in ("role", "skills", "stack", "experience")) for r in records), "JD metadata changed")
    candidates, audit, groups = catalogue_views(records, set(used))
    evidence = read_json(prep / "jd_extraction/jd_extraction_evidence.json")
    _, raw = csv_rows(folder / "dataset/raw/000.csv")
    evidence_check = audit_evidence(raw, evidence)
    catalogue = folder / "catalogue"
    catalogue.mkdir()
    write_lines(catalogue / "records.jsonl", candidates)
    by_id = {r["record_id"]: r for r in audit}
    exported = [dict(record_id=r["record_id"], job_id=r["external_id"], role=r["role"],
        skills_json=json.dumps(r["skills"], ensure_ascii=False), stack_json=json.dumps(r["stack"], ensure_ascii=False),
        experience_json=json.dumps(r["experience"], ensure_ascii=False, sort_keys=True), group_id=r["group_id"],
        source_group=r["source_group"], source_exposure=r["exposure"], benchmark_exposure=by_id[r["record_id"]]["benchmark_exposure"],
        text_sha256=r["normalized_text_sha256"], metadata_flags_json=json.dumps(by_id[r["record_id"]]["metadata_flags"]),
        match_text=r["text_normalized"]) for r in candidates]
    require(exported, "No eligible JD")
    write_csv(catalogue / "jobs.csv", exported, tuple(exported[0]))
    write_json(catalogue / "groups.json", groups)
    write_json(catalogue / "group_representatives.json", dict(record_ids=[g["representative_id"] for g in groups],
        policy="Optional group-level evaluation view; lexical lowest ID per group; does not remove rows from full catalogue"))
    write_json(catalogue / "ids.json", dict(record_ids=[r["record_id"] for r in candidates], external_ids=[r["external_id"] for r in candidates]))
    write_json(catalogue / "metadata_evidence.json", [e for e in evidence if e["job_id"] in {r["external_id"] for r in candidates}])
    write_lines(folder / "jd_audit.jsonl", audit)
    observed = [r for r in source_records if r["kind"] == "cv" and r["namespace"] == "independent-careers-v3"]
    write_json(folder / "completed_benchmark_exposure.json", dict(
        cv_records=[dict(record_id=r["record_id"], source_group=r["source_group"], template_group=r["template_group"],
                         group_id=r["group_id"], future_use="development/regression") for r in observed],
        jd_record_ids=sorted(used), jd_related_record_ids=sorted(r["record_id"] for r in candidates
                            if by_id[r["record_id"]]["benchmark_exposure"] in {"completed_benchmark", "same_group_as_completed_benchmark"}),
        note="New exposure overlay only. Historical source exposure and completed split remain byte-for-byte unchanged."))
    workload = coverage_plan(candidates, observed)
    write_json(folder / "cv_expansion_plan.json", workload)
    summary = dict(version=VERSION, source_jd_count=len(records), catalogue_count=len(candidates),
        dispositions=dict(Counter(r["disposition"] for r in audit)), original_development_related=sum(r["development_only"] for r in records),
        catalogue_groups=len(groups), groups_with_multiple_candidates=sum(len(g["record_ids"]) > 1 for g in groups),
        candidate_rows_in_multi_groups=sum(len(g["record_ids"]) for g in groups if len(g["record_ids"]) > 1),
        original_catalogue_count=len(used), added_jd_count=len(candidates)-len(used),
        catalogue_benchmark_exposure=dict(Counter(by_id[r["record_id"]]["benchmark_exposure"] for r in candidates)),
        role_distribution=dict(Counter(r["role"] or "unknown" for r in candidates)),
        metadata_missing={f: sum(not r[f] for r in candidates) for f in ("role", "skills", "stack", "experience")},
        metadata_fields_present_count=sum(all(bool(r[f]) for f in ("role", "skills", "stack", "experience")) for r in candidates),
        evidence=evidence_check, identity_preservation=identity, import_summary=imported, workload=workload,
        data_analyst=read_json(prep / "handoff_report.json")["data_analyst"],
        input_manifests=dict(preparation=prep_hash, completed_benchmark=benchmark_hash),
        pairs_created=0, labels_created=0, models_trained=0, cv_split_created=False, final_test_ready=False,
        source_csv_unchanged=3, pilot_files_unchanged=len(protected)-3,
        limitations=["Technical gate is not semantic metadata accuracy; unknown remains unknown",
                     "All roles are retained; existing five-role CV cohort does not cover all jobs",
                     "Multiple records in a near/source group are not independent examples",
                     "Completed benchmark CVs are regression only; fresh final test needs new unused CV groups",
                     "No old model/package or 50-JD metrics have been changed to claim 788-JD evaluation"])
    write_json(folder / "summary.json", summary)
    shutil.copyfile(prep / "protected_input_hashes.json", folder / "protected_input_hashes.json")
    verify(prep, "pretraining-ready")
    verify(benchmark, "step4-experiment")
    require(file_hash(prep / "manifest.json") == prep_hash and file_hash(benchmark / "manifest.json") == benchmark_hash,
            "Historical run changed")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Original input/pilot changed during import")
    seal(folder, "jd-catalogue-expansion", dict(preparation_manifest_sha256=prep_hash, benchmark_manifest_sha256=benchmark_hash,
                                             catalogue_count=len(candidates), final_test_ready=False))
    return summary
