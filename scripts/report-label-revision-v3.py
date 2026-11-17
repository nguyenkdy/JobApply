"""Verify two v3 runs and write aggregate-only documentation from their artifacts."""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import file_hash, fresh_folder, read_json, require, write_json  # noqa: E402
from ml_data.policies.__main__ import check  # noqa: E402


def main(first, second, log, output):
    checks = [check(p) for p in (first, second)]
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], "Repeated runs differ")
    text = log.read_text(encoding="utf-16" if log.read_bytes().startswith(b"\xff\xfe") else "utf-8-sig")
    tests = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+OK\s*$", text)
    require(tests, "Successful complete test log required")
    summary = read_json(first / "summary.json")
    output = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(summary=summary, checks=checks, identical_files=len(maps[0]),
        first=first.as_posix(), repeat=second.as_posix(), manifest_sha256=file_hash(first / "manifest.json"),
        tests=dict(passed=int(tests[1]), seconds=float(tests[2]), log_sha256=file_hash(log)))
    write_json(output / "20261117-label-revision-v3.json", receipt)
    write_json(output / "technical_proxy_v3.json", read_json(first / "policy.json"))
    doc = (first / "report.md").read_text(encoding="utf-8")
    before, now = summary["before_labels"], summary["labels"]
    labels = "\n".join(f"| {name} | {before[key]:,} | {now[key]:,} |" for key, name in (("0", "Nhãn 0"), ("1", "Nhãn 1"), ("2", "Nhãn 2"), ("unlabeled", "Chưa nhãn")))
    gap_names = dict(not_exact_occupation="Chưa cùng nghề cụ thể", no_mandatory_technology="Chưa đọc được điều kiện công nghệ bắt buộc",
        no_scoped_duration="Chưa đọc được thời lượng có scope", mandatory_skill_unknown="CV chưa đủ bằng chứng cho kỹ năng bắt buộc",
        duration_unknown="Chưa đối chiếu được thời lượng cùng scope", unconsumed_requirement="Còn yêu cầu chưa đọc hết hoặc khoảng thời gian chưa rõ")
    gaps = "\n".join(f"- {gap_names[k]}: {v:,} cặp nhãn 1." for k, v in summary["label_one_gaps_overlapping"].items())
    blank_names = dict(occupation_transfer_without_task_evidence="Khác nghề, chưa có bằng chứng nhiệm vụ chung",
        unresolved_occupation_and_tasks="Chưa xác định được nghề và nhiệm vụ JD",
        outside_software_scope="Ngoài phạm vi benchmark phần mềm",
        no_exact_shared_skill="Chưa có kỹ năng chung theo bằng chứng đã đọc",
        no_jd_core_skill="Chưa có bằng chứng kỹ năng cốt lõi của JD", no_cv_affirmative_skill="CV chưa có bằng chứng kỹ năng")
    blank_table = "\n".join(f"| {blank_names[k]} | {v:,} |" for k, v in summary["blank_reasons_exclusive"].items())
    first_ps = str(first).replace("/", "\\")
    doc += f"""
## So với v2 và kiểm chứng

| Trạng thái | v2 | v3 |
|---|---:|---:|
{labels}

Hai run `{first.as_posix()}` và `{second.as_posix()}` có **{len(maps[0])}/{len(maps[0])} file giống byte**. Checker xác minh nguồn v2, dựng lại facts/nhãn/bằng chứng, tổng hợp và báo cáo; kiểm offset về câu gốc. **{tests[1]} test đạt**, {float(tests[2]):.3f} giây. Nguồn CSV, pilot, CV, lineage, partition và nhãn v2 giữ nguyên; 50 file bảo vệ khớp byte, bốn mã/lock chỉ chấp nhận khác CRLF/LF đã chứng minh từ trước. Không đổi API/UI/Docker/VM.

Run `20261117_label_revision_v3_01` là snapshot trung gian trước bổ sung chốt chặn câu thay thế/phủ định và bỏ scope suy đoán từ “development experience”; giữ nguyên để truy vết, không dùng làm bản hiện hành.

[Receipt sinh từ run](reports/20261117-label-revision-v3.json), [policy](data_configs/technical_proxy_v3.json), [bàn giao v2](label_revision_v2.md).

Giải thích các nhóm ô trống, mỗi cặp chỉ thuộc một dòng theo thứ tự dừng của luật:

| Lý do chưa kết luận | Cặp |
|---|---:|
{blank_table}

Các điều kiện ngăn nhãn 2 dưới đây có thể chồng lấn, không cộng thành tổng:

{gaps}

## Mã và cách kiểm lại

- `ml_data/policies/technical_v3.py`: phần mở rộng cú pháp, dùng nguyên quy tắc quyết định v2.
- `ml_data/policies/__main__.py`: tạo/check run v3, manifest và chẩn đoán.
- `tests/ml/test_policy_v3.py`: fixture ngữ pháp và schema canonical, giữ nhãn/partition/exposure đúng hợp đồng.
- `scripts/report-label-revision-v3.py`: sinh tài liệu và receipt sau khi kiểm hai run.

Không sửa module v2 đã đóng băng. Package con được snapshot riêng ở `policy_source/` và đưa vào manifest/fingerprint v3; mã cũ vẫn ở `tool_source/`.

```powershell
Set-Location D:\\JobApply
$pythonML = '.\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe'
& $pythonML -m ml_data.policies check --artifact '.\\{first_ps}'
if ($LASTEXITCODE -ne 0) {{ throw 'V3 check failed' }}

$v3Out = '.\\ml_data_runs\\label_revision_v3_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_data.policies prepare --parent .\\ml_data_runs\\20261117_label_revision_v2_02 --output $v3Out
if ($LASTEXITCODE -ne 0) {{ throw 'V3 preparation failed' }}
```

Đây là kết quả đã thực hiện của lượt v3. Chưa tạo CV mới, chưa khóa phương pháp cuối cùng, chưa xây holdout mới hoặc huấn luyện. Việc tiếp theo là xử lý các nhóm câu chưa hiểu theo `clause_changes.jsonl`/`jd_facts.json` và các khoảng trống bằng chứng CV, không đổi ô trống thành 0. Nhãn tổng hợp từ quy tắc vẫn chỉ là proxy; chưa chứng minh chất lượng trên ứng viên thật.
"""
    (output / "label_revision_v3.md").write_text(doc, encoding="utf-8", newline="\n")
    print(dict(identical_files=len(maps[0]), tests=int(tests[1]), labels=now))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "log", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    main(args.first, args.second, args.log, args.output)
