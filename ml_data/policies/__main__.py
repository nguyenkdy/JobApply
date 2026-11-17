"""Prepare/check an additive v3 development revision without changing frozen v2."""
import argparse
from collections import Counter
from pathlib import Path
import platform
import shutil
import sys
import unicodedata

from ml_data.common import ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines, require, seal, verify, write_csv, write_json, write_lines
from ml_data.input_contract import verify_execution_contract
from ml_data.label_revision import check_revision
from ml_data.readiness_audit import sha_bytes
from . import technical_v3 as policy

TYPE = "development-label-revision-v3"


def fingerprints(base=None):
    base = Path(base or ROOT / "ml_data")
    return {p.relative_to(base).as_posix(): dict(raw_sha256=file_hash(p), lf_sha256=sha_bytes(p.read_bytes().replace(b"\r\n", b"\n")))
            for p in sorted(base.rglob("*.py"))}


def blank_reason(cv, jd, result):
    if result["reason"] != "insufficient_affirmative_evidence":
        return result["reason"]
    if result["relation"] == "unresolved_function_transfer":
        return "occupation_transfer_without_task_evidence"
    if not cv["skills"]:
        return "no_cv_affirmative_skill"
    if not jd["skills"]:
        return "no_jd_core_skill"
    return "no_exact_shared_skill"


def compute(parent):
    old_jd = read_json(parent / "jd_facts.json")
    cvs = read_json(parent / "cv_facts.json")
    jd = {key: policy.jd_facts(value) for key, value in old_jd.items()}
    fields, old_rows = csv_rows(parent / "labels.csv")
    rows, evidence, changes = [], [], []
    blanks, gaps = Counter(), Counter()
    for key, facts in jd.items():
        for clause in facts["clauses"]:
            previous = old_jd[key]["clauses"][clause["parent_clause_index"]]
            span, source = clause["evidence"], previous["evidence"]
            require(span["field"] == source["field"] and source["start"] <= span["start"] < span["end"] <= source["end"], "Evidence escapes parent")
            require(source["quote"][span["start"]-source["start"]:span["end"]-source["start"]] == span["quote"], "Evidence differs from parent")
            if previous["state"] != clause["state"] or source != span:
                changes.append(dict(jd_id=key, before_state=previous["state"], before_reason=previous["reason"], after_state=clause["state"],
                    after_reason=clause["reason"], evidence=span, parent_clause_index=clause["parent_clause_index"]))
    for old in old_rows:
        cv, job = cvs[old["cv_id"]], jd[old["jd_id"]]
        decision = policy.judge(cv, job)
        row = dict(old, **{key: decision[key] for key in ("label_status", "relevance_0_1_2", "reason")})
        require(row["effective_exposure"] == "development" and row["evaluation_eligible"] == "false", "Holdout exposure changed")
        rows.append(row)
        evidence.append(dict(pair_id=row["pair_id"], cv_fact=row["cv_id"], jd_fact=row["jd_id"], **decision))
        if not row["relevance_0_1_2"]:
            blanks[blank_reason(cv, job, decision)] += 1
        if row["relevance_0_1_2"] == "1":
            flags = dict(not_exact_occupation=decision["relation"] != "same_specific_occupation",
                no_mandatory_technology=not decision["mandatory_states"], no_scoped_duration=not decision["duration_states"],
                mandatory_skill_unknown=any(c["state"] == "unknown" for c in decision["mandatory_states"]),
                duration_unknown=any(c["state"] == "unknown" for c in decision["duration_states"]),
                unconsumed_requirement=bool(decision["unresolved_clause_indices"]))
            gaps.update(k for k, value in flags.items() if value)
    def label_counts(items):
        return {k: sum((r["relevance_0_1_2"] or "unlabeled") == k for r in items) for k in ("0", "1", "2", "unlabeled")}
    summary = dict(version=policy.VERSION, cv_count=len(cvs), jd_count=len(jd), pair_count=len(rows), labels=label_counts(rows),
        before_labels=label_counts(old_rows),
        partitions={p: dict(total=sum(r["partition"] == p for r in rows), labels=label_counts([r for r in rows if r["partition"] == p])) for p in ("train", "validation", "test")},
        transitions=dict(Counter((old["relevance_0_1_2"] or "unlabeled")+"->"+(new["relevance_0_1_2"] or "unlabeled") for old, new in zip(old_rows, rows, strict=True))),
        blank_reasons_exclusive=dict(blanks), label_one_gaps_overlapping=dict(gaps),
        parser=dict(jd_with_mandatory_technology=sum(any(c["state"] == "mandatory" for c in j["clauses"]) for j in jd.values()),
            jd_with_parsed_duration=sum(any(c["state"] == "duration" for c in j["clauses"]) for j in jd.values()),
            clause_states=dict(Counter(c["state"] for j in jd.values() for c in j["clauses"])),
            unresolved_reasons=dict(Counter(c["reason"] for j in jd.values() for c in j["clauses"] if c["state"] == "unresolved")),
            changed_jd_count=len({c["jd_id"] for c in changes})),
        models_trained=0, ready_for_training=False, independent_test_cv_count=0,
        exposure="All CV remain development; original partitions diagnostic only",
        scope="Technical proxy, not gold, hiring accuracy or independent evaluation; counts do not measure semantic accuracy")
    require(sum(blanks.values()) == summary["labels"]["unlabeled"], "Blank census differs")
    return fields, rows, evidence, jd, changes, summary


def report(summary):
    counts = summary["labels"]
    parts = "\n".join(f"| {p} (cũ) | {s['total']} | {s['labels']['0']} | {s['labels']['1']} | {s['labels']['2']} | {s['labels']['unlabeled']} |" for p, s in summary["partitions"].items())
    blanks = "\n".join(f"- `{k}`: {v:,}" for k, v in sorted(summary["blank_reasons_exclusive"].items()))
    return f"""# Parser và nhãn kỹ thuật v3 — development

Đã xử lý {summary['pair_count']:,} cặp của {summary['cv_count']} CV synthetic và {summary['jd_count']} JD: **{counts['0']} nhãn 0, {counts['1']:,} nhãn 1, {counts['2']} nhãn 2, {counts['unlabeled']:,} cặp chưa nhãn**. Chưa train. Số nhãn và độ phủ không chứng minh độ chính xác ngữ nghĩa.

V3 thêm các mẫu thời lượng khớp toàn câu, prefix kỹ năng và ưu tiên cuối câu có phạm vi rõ. Tách câu có kiểm tra offset; phần còn chưa hiểu giữ unresolved. Không gán thời gian từng công nghệ từ tổng kinh nghiệm. Các phủ định, điều kiện, lựa chọn và scope mơ hồ vẫn bị chặn. Bằng chứng và thay đổi từng mệnh đề nằm trong `clause_changes.jsonl`; bản gốc và nhãn v2 không bị sửa.

Parser có điều kiện công nghệ bắt buộc đọc được ở **{summary['parser']['jd_with_mandatory_technology']} JD**, thời lượng có scope ở **{summary['parser']['jd_with_parsed_duration']} JD**. Các lý do chưa hiểu nằm trong `summary.json`; phần chuẩn hóa này chưa giải quyết toàn bộ nội dung tự nhiên.

| Partition gốc, chỉ chẩn đoán | Cặp | 0 | 1 | 2 | Trống |
|---|---:|---:|---:|---:|---:|
{parts}

## Nguyên nhân ô trống theo luật hiện tại — loại trừ nhau

{blanks}

Đây là lý do thuật toán dừng, không chứng nhận sự thật rằng CV/JD không liên quan. `label_one_gaps_overlapping` trong summary chỉ ra các điều kiện còn thiếu để nhãn 1 lên nhãn 2; các cờ có thể trùng nhau.

## Điều kiện trước huấn luyện

Cả 120 CV / 12 ngân hàng tiếp tục là development. Giữ nguyên lineage, seed và partition; không có test độc lập cho v3. Cần tiếp tục xử lý mẫu câu chưa hiểu và thông tin thiếu bằng bằng chứng; không viết lại CV để khớp JD. Khóa phương pháp trước khi tiếp nhận nhóm đánh giá mới. Không tự gọi nhãn là gold, không tạo điểm Recall/NDCG trên ô trống. Data Analyst vẫn là mục tiêu, cần JD đủ điều kiện riêng, không thay bằng Data Engineer.
"""


def prepare(parent, output):
    parent = Path(parent).resolve()
    check_revision(parent)
    code = fingerprints()
    parent_hash = file_hash(parent / "manifest.json")
    fields, rows, evidence, jd, changes, summary = compute(parent)
    folder = fresh_folder(output, (parent,))
    write_json(folder / "policy.json", policy.POLICY)
    write_json(folder / "input_receipt.json", dict(parent_path=parent.relative_to(ROOT).as_posix(), parent_manifest_sha256=parent_hash))
    write_json(folder / "execution_fingerprints.json", code)
    for name in ("cv_facts.json", "source_assignments.jsonl", "exposure_overlay.json", "input_contract.json"):
        shutil.copyfile(parent / name, folder / name)
    write_json(folder / "runtime.json", dict(python=sys.version, platform=platform.platform(), unicode_version=unicodedata.unidata_version,
        dependencies="Python standard library only; no model downloads/inference"))
    write_json(folder / "jd_facts.json", jd)
    write_csv(folder / "labels.csv", rows, fields)
    write_lines(folder / "evidence.jsonl", evidence)
    write_lines(folder / "clause_changes.jsonl", changes)
    write_json(folder / "summary.json", summary)
    (folder / "report.md").write_text(report(summary), encoding="utf-8", newline="\n")
    shutil.copytree(Path(__file__).parent, folder / "policy_source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    require(fingerprints() == code, "Execution code changed during run")
    verify(parent, "development-label-revision")
    require(file_hash(parent / "manifest.json") == parent_hash, "Parent changed during run")
    seal(folder, TYPE, dict(policy_version=policy.VERSION, models_trained=0))
    return summary


def check(folder):
    folder = Path(folder).resolve()
    verify(folder, TYPE)
    receipt = read_json(folder / "input_receipt.json")
    parent = (ROOT / receipt["parent_path"]).resolve()
    require(parent.is_relative_to(ROOT), "Parent path escapes workspace")
    require(file_hash(parent / "manifest.json") == receipt["parent_manifest_sha256"], "Parent changed")
    check_revision(parent)
    code = read_json(folder / "execution_fingerprints.json")
    archived = fingerprints(folder / "tool_source")
    archived.update({"policies/"+k: v for k, v in fingerprints(folder / "policy_source").items()})
    require(code == archived, "Code snapshot differs from declared fingerprints")
    verify_execution_contract(code, fingerprints())
    require(read_json(folder / "policy.json") == policy.POLICY, "Policy changed")
    fields, rows, evidence, jd, changes, summary = compute(parent)
    require(csv_rows(folder / "labels.csv") == (fields, rows), "Labels do not reproduce")
    for name, expected in (("evidence.jsonl", evidence), ("clause_changes.jsonl", changes)):
        require(read_lines(folder / name) == expected, "Evidence/changes differ")
    require(read_json(folder / "jd_facts.json") == jd and read_json(folder / "summary.json") == summary, "Facts/summary differ")
    require((folder / "report.md").read_text(encoding="utf-8") == report(summary), "Report differs")
    for name in ("cv_facts.json", "source_assignments.jsonl", "exposure_overlay.json", "input_contract.json"):
        require(file_hash(folder / name) == file_hash(parent / name), "Immutable parent input changed")
    return dict(verified=True, labels=summary["labels"], models_trained=0, ready_for_training=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare")
    command.add_argument("--parent", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("check")
    command.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.parent, args.output) if args.command == "prepare" else check(args.artifact)
    print(result)


if __name__ == "__main__":
    main()
