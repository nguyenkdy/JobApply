"""Offline task-based revision and free-title pair inspection; no app/model/network changes."""
import argparse
from collections import Counter
from pathlib import Path
import platform
import shutil
import sys

from ml_data.common import ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines, require, seal, verify, write_csv, write_json, write_lines
from ml_data.input_contract import verify_execution_contract, verify_inputs
from ml_data.policies.__main__ import fingerprints
from . import policy

TYPE = "task-evidence-development-v4"


def source_inputs(parent):
    verify(parent, "development-label-revision-v3")
    verify_execution_contract(read_json(parent / "execution_fingerprints.json"), fingerprints())
    previous = read_json(parent / "input_receipt.json")
    v2 = ROOT / previous["parent_path"]
    require(file_hash(v2 / "manifest.json") == previous["parent_manifest_sha256"], "v2 parent changed")
    verify(v2, "development-label-revision")
    receipt = read_json(v2 / "input_receipt.json")
    intake, audit = ROOT / receipt["intake_path"], ROOT / receipt["audit_path"]
    require(file_hash(intake / "manifest.json") == receipt["intake_manifest_sha256"], "Intake changed")
    require(file_hash(audit / "manifest.json") == receipt["audit_manifest_sha256"], "Audit changed")
    contract = verify_inputs(intake, audit)
    require(contract == read_json(parent / "input_contract.json"), "Protected inputs changed")
    return intake, contract


def compute(parent, intake):
    records = {r["record_id"]: r for r in read_lines(intake / "records.jsonl")}
    original_cv, original_jd = read_json(parent / "cv_facts.json"), read_json(parent / "jd_facts.json")
    cvs = {cid: policy.cv_facts(records[cid]["text_original"], old,
        body_offset=records[cid]["text_original"].find("\n")+1) for cid, old in original_cv.items()}
    jobs = {jid: policy.job_facts(records[jid], old) for jid, old in original_jd.items()}
    for kind, facts in (("cv", cvs), ("jd", jobs)):
        for rid, values in facts.items():
            spans = [*values["skills"].values(), *(s for seq in values["functions"].values() for s in seq)]
            for span in spans:
                text = records[rid]["text_original"] if kind == "cv" else policy.v2.source_field(records[rid], span["field"])
                require(text[span["start"]:span["end"]] == span["quote"], "Evidence offsets differ from input")
    fields, old_rows = csv_rows(parent / "labels.csv")
    rows, evidence = [], []
    for old in old_rows:
        cv, jd = cvs[old["cv_id"]], jobs[old["jd_id"]]
        decision = policy.judge(cv, jd)
        # Check every actual pair, not only a few demo titles.
        renamed = policy.judge(dict(cv, role="Unseen occupation XYZ"), dict(jd, role="", role_specific=False, role_overlay={}))
        require(decision == renamed, "Decision depends on occupation name")
        row = dict(old, **{k: decision[k] for k in ("label_status", "relevance_0_1_2", "reason")})
        require(row["effective_exposure"] == "development" and row["evaluation_eligible"] == "false", "Exposure changed")
        rows.append(row)
        evidence.append(dict(pair_id=row["pair_id"], cv_fact=row["cv_id"], jd_fact=row["jd_id"], **decision))
    def counts(items):
        return {k: sum((r["relevance_0_1_2"] or "unlabeled") == k for r in items) for k in ("0", "1", "2", "unlabeled")}
    summary = dict(version=policy.VERSION, cv_count=len(cvs), jd_count=len(jobs), pair_count=len(rows), labels=counts(rows), before_labels=counts(old_rows),
        partitions={p: dict(total=sum(r["partition"] == p for r in rows), labels=counts([r for r in rows if r["partition"] == p])) for p in ("train", "validation", "test")},
        transitions=dict(Counter((a["relevance_0_1_2"] or "unlabeled")+"->"+(b["relevance_0_1_2"] or "unlabeled") for a, b in zip(old_rows, rows, strict=True))),
        blank_reasons=dict(Counter(r["reason"] for r in rows if not r["relevance_0_1_2"])),
        task_coverage=dict(cv_before=sum(bool(c["functions"]) for c in original_cv.values()), cv_after=sum(bool(c["functions"]) for c in cvs.values()),
            jd_before=sum(bool(j["functions"]) for j in original_jd.values()), jd_after=sum(bool(j["functions"]) for j in jobs.values()),
            functions_cv=dict(Counter(k for c in cvs.values() for k in c["functions"])), functions_jd=dict(Counter(k for j in jobs.values() for k in j["functions"]))),
        jd_complete_bounded_requirements=sum(j["requirement_coverage"]["complete_bounded_grammar"] for j in jobs.values()),
        explicit_dataset_exclusions_preserved=sum(j.get("outside_scope", False) for j in jobs.values()),
        positive_pairs_with_unknown_jd_role=sum(r["relevance_0_1_2"] in {"1", "2"} and not jobs[r["jd_id"]]["role"] for r in rows),
        source_cv_roles=dict(Counter(records[c]["role"] for c in cvs)),
        title_ablation_checked_pairs=len(rows), occupation_whitelist_used=False, external_api_calls=0, llm_calls=0, models_trained=0,
        independent_test_cv_count=0, ready_for_training=False,
        interpretation="Development proxy only; title invariance does not establish generalization to arbitrary new occupations")
    return fields, rows, evidence, cvs, jobs, summary


def prepare(parent, output):
    parent = Path(parent).resolve()
    intake, contract = source_inputs(parent)
    before = file_hash(parent / "manifest.json")
    code = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    fields, rows, evidence, cvs, jobs, summary = compute(parent, intake)
    folder = fresh_folder(output, (parent, intake))
    for name in ("source_assignments.jsonl", "exposure_overlay.json", "input_contract.json"):
        shutil.copyfile(parent / name, folder / name)
    write_json(folder / "policy.json", policy.POLICY)
    write_json(folder / "cv_facts.json", cvs)
    write_json(folder / "jd_facts.json", jobs)
    write_csv(folder / "labels.csv", rows, fields)
    write_lines(folder / "evidence.jsonl", evidence)
    write_json(folder / "summary.json", summary)
    write_json(folder / "runtime.json", dict(python=sys.version, platform=platform.platform(), dependencies="Python standard library; no LLM/runtime/model downloads"))
    write_json(folder / "input_receipt.json", dict(parent_path=parent.relative_to(ROOT).as_posix(), parent_manifest_sha256=before,
        intake_manifest_sha256=file_hash(intake / "manifest.json"), source_code=code))
    shutil.copytree(Path(__file__).parent, folder / "task_source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    require(source_inputs(parent) == (intake, contract) and file_hash(parent / "manifest.json") == before, "Inputs changed during revision")
    require(code == {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}, "Task code changed during revision")
    seal(folder, TYPE, dict(policy_version=policy.VERSION, models_trained=0, llm_calls=0))
    return summary


def check(folder):
    folder = Path(folder).resolve()
    verify(folder, TYPE)
    receipt = read_json(folder / "input_receipt.json")
    parent = (ROOT / receipt["parent_path"]).resolve()
    require(parent.is_relative_to(ROOT) and file_hash(parent / "manifest.json") == receipt["parent_manifest_sha256"], "Parent changed")
    intake, _ = source_inputs(parent)
    require(file_hash(intake / "manifest.json") == receipt["intake_manifest_sha256"], "Intake changed")
    require(read_json(folder / "policy.json") == policy.POLICY, "Policy changed")
    for name, sha in receipt["source_code"].items():
        archived, current = folder / "task_source" / name, Path(__file__).parent / name
        require(file_hash(archived) == sha and archived.read_bytes().replace(b"\r\n", b"\n") == current.read_bytes().replace(b"\r\n", b"\n"), "Task source changed")
    fields, rows, evidence, cvs, jobs, summary = compute(parent, intake)
    require(csv_rows(folder / "labels.csv") == (fields, rows) and read_lines(folder / "evidence.jsonl") == evidence, "Labels/evidence differ")
    require(read_json(folder / "cv_facts.json") == cvs and read_json(folder / "jd_facts.json") == jobs, "Facts differ")
    require(read_json(folder / "summary.json") == summary, "Summary differs")
    for name in ("source_assignments.jsonl", "exposure_overlay.json", "input_contract.json"):
        require(file_hash(folder / name) == file_hash(parent / name), "Immutable input overlay changed")
    return dict(verified=True, pair_count=len(rows), title_ablation_checked_pairs=len(rows), labels=summary["labels"], models_trained=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("check")
    p.add_argument("--artifact", type=Path, required=True)
    p = commands.add_parser("inspect-pair")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.parent, args.output))
    elif args.command == "check":
        print(check(args.artifact))
    else:
        result = policy.inspect_pair(read_json(args.input))
        write_json(args.output, result)
        print(result["decision"])
