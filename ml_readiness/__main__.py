"""Inventory document evidence versus frozen v3 facts; never generate relevance labels."""
import argparse
from collections import Counter
from pathlib import Path
import re
import shutil

from ml_data.common import ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines, require, seal, verify, write_csv, write_json, write_lines
from ml_data.expanded_labels import source_field
from ml_data.policies.__main__ import check as check_v3
from ml_data.technical_policy_v2 import mentions

VERSION = "document-evidence-inventory-v1"
TYPE = "document-evidence-inventory"
TIME = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*\+?\s*(?:năm|tháng|years?|months?)\b", re.I)
MISSING = re.compile(r"không (?:còn|có|đủ)|không.*khai|thiếu|chưa.*ghi|không.*xác nhận|để trống|giữ unknown", re.I)
TIMELINE = re.compile(r"thời gian|thời lượng|số tháng|tổng tháng|tháng làm|tháng kinh nghiệm|mốc|lịch thực hiện|lịch sử|hợp đồng", re.I)
ACTION = re.compile(r"\b(?:viết|sửa|xây dựng|phát triển|triển khai|thiết kế|kiểm thử|kiểm tra|đối chiếu|chuẩn hóa|vận hành|bổ sung|build|develop|implement|design|test|deploy|maintain|manage)\b", re.I)
FIELDS = ("record_id", "kind", "external_id", "group_id", "role", "effective_exposure", "text_present", "role_parsed",
    "task_field_present", "task_functions_parsed", "task_action_cues", "skills_parsed", "technology_cues",
    "duration_parsed", "numeric_time_cues", "duration_unresolved_cues", "explicit_missing_timeline", "duration_status",
    "requirements_field_present", "preferred_field_present", "mandatory_clauses", "unresolved_clauses")


def span_hits(text, field, pattern, category):
    return [dict(field=field, start=m.start(), end=m.end(), quote=m[0], category=category) for m in pattern.finditer(text)]


def missing_timeline(text):
    result = []
    for match in re.finditer(r"[^\n]+?(?:\.(?=\s|$)|$)", text):
        if MISSING.search(match[0]) and TIMELINE.search(match[0]) and not TIME.search(match[0]):
            result.append(dict(field="cv_text", start=match.start(), end=match.end(), quote=match[0], category="explicit_missing_timeline_statement"))
    return result


def contained(span, container):
    return span["field"] == container.get("field", "cv_text") and container["start"] <= span["start"] < span["end"] <= container["end"]


def duration_status(kind, text_present, parsed, numeric_count, unresolved, missing):
    if not text_present:
        return "source_field_empty"
    if kind == "cv" and not parsed and not numeric_count and missing:
        return "source_explicitly_leaves_timeline_unknown"
    if unresolved:
        return "partial_extraction_with_unresolved_cues" if parsed else "numeric_cue_without_parsed_scope"
    if parsed:
        return "parsed_evidence_present_not_semantic_certification"
    if numeric_count:
        return "numeric_cues_only_optional_or_unclassified"
    return "no_numeric_cue_detected_absence_not_proven"


def inspect_record(record, facts):
    kind = record["kind"]
    if kind == "cv":
        texts = {"cv_text": record["text_original"]}
        duration_field = "cv_text"
        tasks = record["text_original"].partition("\n")[2]
        task_field, task_offset = "cv_text", len(record["text_original"])-len(tasks)
        parsed_durations = [dict(d, field="cv_text") for d in facts["durations"]]
        clauses = []
        missing = missing_timeline(texts["cv_text"])
    else:
        texts = {field: source_field(record, field) for field in ("title_for_matching", "tasks_text", "requirements_text", "preferred_requirements_text")}
        duration_field = "requirements_text"
        tasks, task_field, task_offset = texts["tasks_text"], "tasks_text", 0
        clauses = facts["clauses"]
        parsed_durations = [c["evidence"] for c in clauses if c["state"] == "duration"]
        missing = []
    numeric = span_hits(texts[duration_field], duration_field, TIME, "numeric_duration_cue_not_a_requirement_assertion")
    unresolved = 0
    for cue in numeric:
        explained = any(contained(cue, d) for d in parsed_durations)
        optional = any(c["state"] == "preferred" and contained(cue, c["evidence"]) for c in clauses)
        cue["coverage"] = "parsed_duration" if explained else "preferred_clause" if optional else "unresolved_candidate"
        unresolved += cue["coverage"] == "unresolved_candidate"
    task_cues = span_hits(tasks, task_field, ACTION, "action_word_candidate_not_task_semantics")
    for cue in task_cues:
        cue["start"] += task_offset
        cue["end"] += task_offset
    tech_cues = [dict(field=field, start=a, end=b, quote=q, category="technology_mention_not_requirement", technology=term)
                for field, text in texts.items() for a, b, term, q in mentions(text)]
    observations = [*numeric, *missing, *task_cues, *tech_cues]
    for span in observations:
        require(texts[span["field"]][span["start"]:span["end"]] == span["quote"], "Inventory evidence offset differs")
    row = dict(record_id=record["record_id"], kind=kind, external_id=record["external_id"], group_id=record["group_id"],
        role=facts["role"], effective_exposure="development", text_present=bool(record["text_original"].strip()),
        role_parsed=bool(facts["role"]), task_field_present=bool(tasks.strip()), task_functions_parsed=len(facts["functions"]),
        task_action_cues=len(task_cues), skills_parsed=len(facts["skills"]), technology_cues=len(tech_cues),
        duration_parsed=len(parsed_durations), numeric_time_cues=len(numeric), duration_unresolved_cues=unresolved,
        explicit_missing_timeline=bool(missing), duration_status=duration_status(kind, bool(texts[duration_field].strip()), len(parsed_durations), len(numeric), unresolved, bool(missing)),
        requirements_field_present=bool(texts.get("requirements_text", "").strip()), preferred_field_present=bool(texts.get("preferred_requirements_text", "").strip()),
        mandatory_clauses=sum(c["state"] == "mandatory" for c in clauses), unresolved_clauses=sum(c["state"] == "unresolved" for c in clauses))
    return row, dict(record_id=record["record_id"], text_sha256=record["text_sha256"], observations=observations,
        interpretation="Lexical probes triage extraction, not independent semantic truth or new labels")


def parent_intake(parent):
    v2 = ROOT / read_json(parent / "input_receipt.json")["parent_path"]
    return ROOT / read_json(v2 / "input_receipt.json")["intake_path"]


def inventory(parent):
    intake = parent_intake(parent)
    records = read_lines(intake / "records.jsonl")
    cvs, jobs = read_json(parent / "cv_facts.json"), read_json(parent / "jd_facts.json")
    require({r["record_id"] for r in records} == set(cvs) | set(jobs), "Source inventory coverage differs")
    rows, evidence = [], []
    for record in sorted(records, key=lambda r: (r["kind"], r["record_id"])):
        facts = (cvs if record["kind"] == "cv" else jobs)[record["record_id"]]
        row, item = inspect_record(record, facts)
        rows.append(row)
        evidence.append(item)
    summary = dict(version=VERSION, records=len(rows), labels_unchanged=True, new_labels=0, models_trained=0,
        semantic_accuracy_measured=False, exposure="development_only", complete_semantic_inventory=False,
        interpretation="Source empty and explicit unknown are observed; lexical cues without extraction are candidates, not proven parser errors. No cue is not proof of absent information.",
        by_kind={kind: dict(records=sum(r["kind"] == kind for r in rows),
            duration_status=dict(Counter(r["duration_status"] for r in rows if r["kind"] == kind)),
            nonempty_text=sum(r["text_present"] for r in rows if r["kind"] == kind),
            role_parsed=sum(r["role_parsed"] for r in rows if r["kind"] == kind),
            tasks_nonempty=sum(r["task_field_present"] for r in rows if r["kind"] == kind),
            task_functions_parsed=sum(r["task_functions_parsed"] > 0 for r in rows if r["kind"] == kind),
            action_cues_without_task_function=sum(r["task_action_cues"] > 0 and not r["task_functions_parsed"] for r in rows if r["kind"] == kind),
            technology_cues_without_positive_skill=sum(r["technology_cues"] > 0 and not r["skills_parsed"] for r in rows if r["kind"] == kind),
            requirements_nonempty=sum(r["requirements_field_present"] for r in rows if r["kind"] == kind),
            preferred_field_empty=sum(not r["preferred_field_present"] for r in rows if r["kind"] == kind),
            jd_with_mandatory_clause=sum(r["mandatory_clauses"] > 0 for r in rows if r["kind"] == kind),
            records_with_unresolved_clauses=sum(r["unresolved_clauses"] > 0 for r in rows if r["kind"] == kind)) for kind in ("cv", "jd")},
        cv_duration=dict(no_duration=sum(not c["durations"] for c in cvs.values()),
            employment_or_contract=sum(any(d["kind"] in {"employment", "contract"} for d in c["durations"]) for c in cvs.values()),
            specific_employment_scope=sum(any(d["kind"] in {"employment", "contract"} and d["scope"] != "professional experience" for d in c["durations"]) for c in cvs.values())),
        frozen_pair_summary=read_json(parent / "summary.json"))
    # Deterministic development probes, with no label or model rank used for selection.
    queues = []
    for kind in ("cv", "jd"):
        for state in sorted({r["duration_status"] for r in rows if r["kind"] == kind}):
            candidates = [r for r in rows if r["kind"] == kind and r["duration_status"] == state]
            for r in candidates[:5]:
                queues.append(dict(record_id=r["record_id"], kind=kind, reason=state, exposure="development",
                    selection="first five sorted record IDs per kind/duration status; not representative or holdout"))
    return rows, evidence, queues, summary


def prepare(parent, output):
    parent = Path(parent).resolve()
    check_v3(parent)
    before = file_hash(parent / "manifest.json")
    own = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    rows, evidence, queues, summary = inventory(parent)
    folder = fresh_folder(output, (parent, parent_intake(parent)))
    write_csv(folder / "record_inventory.csv", rows, FIELDS)
    write_lines(folder / "field_evidence.jsonl", evidence)
    write_lines(folder / "extraction_probe_set.jsonl", queues)
    write_json(folder / "summary.json", summary)
    write_json(folder / "input_receipt.json", dict(parent_path=parent.relative_to(ROOT).as_posix(), parent_manifest_sha256=before,
        intake_manifest_sha256=file_hash(parent_intake(parent) / "manifest.json"), parent_labels_sha256=file_hash(parent / "labels.csv"), source_code=own))
    shutil.copytree(Path(__file__).parent, folder / "audit_source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    verify(parent, "development-label-revision-v3")
    require(before == file_hash(parent / "manifest.json"), "Parent changed")
    require(own == {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}, "Audit source changed during run")
    seal(folder, TYPE, dict(new_labels=0, models_trained=0))
    return summary


def check(folder):
    folder = Path(folder).resolve()
    verify(folder, TYPE)
    receipt = read_json(folder / "input_receipt.json")
    parent = (ROOT / receipt["parent_path"]).resolve()
    require(parent.is_relative_to(ROOT), "Parent escapes workspace")
    require(file_hash(parent / "manifest.json") == receipt["parent_manifest_sha256"], "Parent manifest changed")
    check_v3(parent)
    require(file_hash(parent / "labels.csv") == receipt["parent_labels_sha256"], "Parent labels changed")
    require(file_hash(parent_intake(parent) / "manifest.json") == receipt["intake_manifest_sha256"], "Intake changed")
    for name, sha in receipt["source_code"].items():
        archived = folder / "audit_source" / name
        current = Path(__file__).parent / name
        require(file_hash(archived) == sha and archived.read_bytes().replace(b"\r\n", b"\n") == current.read_bytes().replace(b"\r\n", b"\n"), "Audit code changed")
    rows, evidence, queues, summary = inventory(parent)
    actual = csv_rows(folder / "record_inventory.csv")[1]
    require(actual == [{k: str(v) for k, v in r.items()} for r in rows], "Record audit differs")
    require(read_lines(folder / "field_evidence.jsonl") == evidence and read_lines(folder / "extraction_probe_set.jsonl") == queues, "Evidence differs")
    require(read_json(folder / "summary.json") == summary, "Summary differs")
    return dict(verified=True, records=len(rows), labels_unchanged=True, new_labels=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("check")
    p.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.parent, args.output) if args.command == "prepare" else check(args.artifact))
