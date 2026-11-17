"""Prepare a new *development* label revision; keep all old data and partitions immutable."""
from collections import Counter
from pathlib import Path
import platform
import shutil
import sys
import unicodedata

from .common import (ROOT, csv_rows, digest, file_hash, fresh_folder, read_json, read_lines, require,
                     seal, verify, write_csv, write_json, write_lines)
from .expanded_labels import LABEL_FIELDS, expected_pairs, tally
from .input_contract import execution_fingerprints, verify_execution_contract, verify_inputs
from .readiness_audit import sha_bytes
from .readiness_audit import validate_snapshot
from . import technical_policy_v2 as policy


def exposure_overlay(cvs, assignments):
    source = {a["record_id"]: a["partition"] for a in assignments if a["kind"] == "cv"}
    require(set(source) == set(cvs), "CV assignment coverage differs")
    groups = {}
    for cid, record in sorted(cvs.items()):
        group = groups.setdefault(record["group_id"], dict(group_id=record["group_id"], record_ids=[],
            effective_exposure="development", eligible_for_independent_evaluation=False,
            reason="Label policy revised after v1 diagnostics of this cohort, including historical validation/test"))
        group["record_ids"].append(cid)
    return dict(version="policy-revision-exposure-v1", groups=list(groups.values()),
                original_partitions=source, source_assignments_unchanged=True, seed_retries=0,
                original_exposure_preserved_in_source=True, overlay_required=True)


def build_facts(cvs, jobs, original_cv):
    cv = {cid: policy.cv_facts(c, original_cv[cid]) for cid, c in sorted(cvs.items())}
    jd = {jid: policy.jd_facts(j) for jid, j in sorted(jobs.items())}
    for cid, facts in cv.items():
        text = cvs[cid]["text_original"]
        for span in [*facts["skills"].values(), *facts["nonuse"].values(), *facts["durations"],
                     *(s for values in facts["functions"].values() for s in values)]:
            require(text[span["start"]:span["end"]] == span["quote"], "CV derived evidence offset differs")
    from .expanded_labels import source_field
    for jid, facts in jd.items():
        for span in [*facts["skills"].values(), *facts["role_overlay"]["evidence"],
                     *(c["evidence"] for c in facts["clauses"]),
                     *(s for values in facts["functions"].values() for s in values)]:
            text = source_field(jobs[jid], span["field"])
            require(text[span["start"]:span["end"]] == span["quote"], "JD derived evidence offset differs")
    return cv, jd


def revision_rows(intake, cvs, jobs, cv, jd):
    rows, evidence = [], []
    for partition, cid, jid in expected_pairs(intake, jobs):
        pair = "PAIR_" + digest(cid + "|" + jid)[:32]
        result = policy.judge(cv[cid], jd[jid])
        rows.append(dict(pair_id=pair, partition=partition, cv_id=cid, jd_id=jid,
            cv_version=cvs[cid]["normalized_text_sha256"], jd_version=jobs[jid]["normalized_text_sha256"],
            **{key: result[key] for key in ("label_status", "relevance_0_1_2", "reason")},
            evidence_ref="evidence.jsonl#" + pair, effective_exposure="development", evaluation_eligible="false"))
        evidence.append(dict(pair_id=pair, cv_fact=cid, jd_fact=jid, **result))
    return rows, evidence


def summarize(rows, evidence, old_rows, cvs, jobs, cv, jd):
    summary = tally(rows, cvs, jobs)
    old = {r["pair_id"]: r for r in old_rows}
    require(set(old) == {r["pair_id"] for r in rows}, "Revision changed pair population")
    summary.update(version=policy.VERSION, partition_interpretation="Historical partitions for diagnostic comparison only; all groups development",
        full_catalogue_ranking_metrics_allowed=False, ready_for_training=False, final_test_ready=False,
        independent_test_cv_count=0, exposure="development", models_trained=0,
        transitions=dict(Counter((old[r["pair_id"]]["relevance_0_1_2"] or "unlabeled") + "->" + (r["relevance_0_1_2"] or "unlabeled") for r in rows)),
        transitions_by_source_partition={p: dict(Counter((old[r["pair_id"]]["relevance_0_1_2"] or "unlabeled") + "->" + (r["relevance_0_1_2"] or "unlabeled") for r in rows if r["partition"] == p)) for p in ("train", "validation", "test")},
        labeled_with_shared_task_function=sum(e["relation"] == "shared_task_function" and e["relevance_0_1_2"] != "" for e in evidence),
        parser=dict(jd_count=len(jd), clause_states=dict(Counter(c["state"] for j in jd.values() for c in j["clauses"])),
            jd_with_mandatory_technology=sum(any(c["state"] == "mandatory" for c in j["clauses"]) for j in jd.values()),
            jd_with_parsed_duration=sum(any(c["state"] == "duration" for c in j["clauses"]) for j in jd.values()),
            jd_with_task_evidence=sum(bool(j["functions"]) for j in jd.values()), cv_with_task_evidence=sum(bool(c["functions"]) for c in cv.values()),
            occupation_overlay_changes=sum(j["role"] != j["role_overlay"]["previous_role"] for j in jd.values()),
            empty_role_after_overlay=sum(not j["role"] for j in jd.values()),
            generic_role_after_overlay=sum("unspecified" in j["role"] for j in jd.values()),
            outside_software_scope=sum(j["outside_scope"] for j in jd.values()),
            interpretation="Coverage, not accuracy; label changes do not certify semantic correctness"),
        readiness_reason="Development revision after cohort audit. No independent holdout remains; incomplete judgments/classes must be reported. No model fitting.")
    return summary


def prepare_revision(intake, old_labels, audit, output):
    intake, old_labels, audit = [Path(p).resolve() for p in (intake, old_labels, audit)]
    contract = verify_inputs(intake, audit)
    audit_summary = read_json(audit / "summary.json")
    require(audit_summary["inputs"]["labels_manifest_sha256"] == file_hash(old_labels / "manifest.json"), "Audit/label parent differs")
    cvs, jobs, old_cv, _, old_rows, _, _ = validate_snapshot(intake, old_labels)
    fingerprints = execution_fingerprints()
    cv, jd = build_facts(cvs, jobs, old_cv)
    overlay = exposure_overlay(cvs, read_lines(intake / "assignments.jsonl"))
    folder = fresh_folder(output, (intake, old_labels, audit))
    write_json(folder / "policy.json", policy.POLICY)
    write_json(folder / "input_contract.json", contract)
    write_json(folder / "execution_fingerprints.json", fingerprints)
    write_json(folder / "runtime.json", dict(python=sys.version, platform=platform.platform(), unicode_version=unicodedata.unidata_version,
                                             dependencies="Python standard library only; no model downloads/inference"))
    write_json(folder / "exposure_overlay.json", overlay)
    shutil.copyfile(intake / "assignments.jsonl", folder / "source_assignments.jsonl")
    write_json(folder / "cv_facts.json", cv)
    write_json(folder / "jd_facts.json", jd)
    rows, evidence = revision_rows(intake, cvs, jobs, cv, jd)
    write_csv(folder / "labels.csv", rows, (*LABEL_FIELDS, "effective_exposure", "evaluation_eligible"))
    write_lines(folder / "evidence.jsonl", evidence)
    summary = summarize(rows, evidence, old_rows, cvs, jobs, cv, jd)
    write_json(folder / "summary.json", summary)
    write_json(folder / "input_receipt.json", dict(intake_path=intake.relative_to(ROOT).as_posix(), old_labels_path=old_labels.relative_to(ROOT).as_posix(), audit_path=audit.relative_to(ROOT).as_posix(),
        intake_manifest_sha256=file_hash(intake / "manifest.json"), old_labels_manifest_sha256=file_hash(old_labels / "manifest.json"), audit_manifest_sha256=file_hash(audit / "manifest.json")))
    require(verify_inputs(intake, audit) == contract, "Inputs changed while labeling")
    verify(old_labels, "expanded-proxy-labels")
    require(execution_fingerprints() == fingerprints, "Execution code changed during run")
    seal(folder, "development-label-revision", dict(policy_version=policy.VERSION, final_test_ready=False, models_trained=0))
    return {key: summary[key] for key in ("labels", "partitions", "parser", "missing_train_classes", "ready_for_training", "independent_test_cv_count")}


def check_revision(artifact):
    artifact = Path(artifact)
    verify(artifact, "development-label-revision")
    receipt = read_json(artifact / "input_receipt.json")
    intake, old_labels, audit = [ROOT / receipt[k] for k in ("intake_path", "old_labels_path", "audit_path")]
    for path, key in ((intake, "intake_manifest_sha256"), (old_labels, "old_labels_manifest_sha256"), (audit, "audit_manifest_sha256")):
        require(file_hash(path / "manifest.json") == receipt[key], "Parent manifest changed")
    require(read_json(artifact / "input_contract.json") == verify_inputs(intake, audit), "Input contract changed")
    require(read_json(artifact / "policy.json") == policy.POLICY, "Wrong policy version")
    saved = read_json(artifact / "execution_fingerprints.json")
    archived = {p.name: dict(raw_sha256=file_hash(p), lf_sha256=sha_bytes(p.read_bytes().replace(b"\r\n", b"\n")))
                for p in (artifact / "tool_source").glob("*.py")}
    require(saved == archived, "Declared execution fingerprints differ from archived source")
    verify_execution_contract(saved, execution_fingerprints())
    cvs, jobs, old_cv, _, old_rows, _, _ = validate_snapshot(intake, old_labels)
    cv, jd = build_facts(cvs, jobs, old_cv)
    require(read_json(artifact / "cv_facts.json") == cv and read_json(artifact / "jd_facts.json") == jd, "Facts do not reproduce source evidence")
    assignments = read_lines(intake / "assignments.jsonl")
    require(file_hash(artifact / "source_assignments.jsonl") == file_hash(intake / "assignments.jsonl"), "Source partitions changed")
    require(read_json(artifact / "exposure_overlay.json") == exposure_overlay(cvs, assignments), "Development exposure lost")
    rows, evidence = revision_rows(intake, cvs, jobs, cv, jd)
    require(csv_rows(artifact / "labels.csv")[1] == rows and read_lines(artifact / "evidence.jsonl") == evidence, "Labels/evidence do not reproduce policy")
    summary = summarize(rows, evidence, old_rows, cvs, jobs, cv, jd)
    require(read_json(artifact / "summary.json") == summary, "Summary differs from rows")
    return dict(verified=True, pair_count=len(rows), labels=summary["labels"], ready_for_training=False, independent_test_cv_count=0)
