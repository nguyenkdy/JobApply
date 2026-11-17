"""Verify two v4 task-matching runs and generate the public handoff report."""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, require, write_json  # noqa: E402
from ml_task_matching.__main__ import check  # noqa: E402
from ml_task_matching.policy import inspect_pair  # noqa: E402


def main(first, second, log, output):
    first, second, log = Path(first), Path(second), Path(log)
    checks = [check(p) for p in (first, second)]
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], "Repeated v4 runs differ")
    text = log.read_text(encoding="utf-16" if log.read_bytes().startswith(b"\xff\xfe") else "utf-8-sig")
    tests = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+OK\s*$", text)
    require(tests, "Successful complete test log required")
    summary = read_json(first / "summary.json")
    policy = read_json(first / "policy.json")
    unseen_path = ROOT / "docs/ml/examples/unseen_title_pair.json"
    unknown_path = ROOT / "docs/ml/examples/unknown_task_pair.json"
    unseen_example = inspect_pair(read_json(unseen_path))
    unknown_example = inspect_pair(read_json(unknown_path))
    require(unseen_example["decision"]["relevance_0_1_2"] == "2" and not unseen_example["decision"]["title_used_for_decision"], "Unseen title example failed")
    require(unknown_example["decision"]["relevance_0_1_2"] == "" and unknown_example["decision"]["shared_skills"] == ["python"], "Unknown task example failed")
    folder = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(
        summary=summary,
        checks=checks,
        identical_files=len(maps[0]),
        first=first.as_posix(),
        repeat=second.as_posix(),
        manifest_sha256=file_hash(first / "manifest.json"),
        tests=dict(passed=int(tests[1]), seconds=float(tests[2]), log_sha256=file_hash(log)),
        examples=dict(
            unseen_title_pair=dict(path="docs/ml/examples/unseen_title_pair.json", sha256=file_hash(unseen_path), decision=unseen_example["decision"]),
            unknown_task_pair=dict(path="docs/ml/examples/unknown_task_pair.json", sha256=file_hash(unknown_path), decision=unknown_example["decision"]),
        ),
    )
    write_json(folder / "20261117-task-matching-v4.json", receipt)
    write_json(folder / "task_evidence_proxy_v4.json", policy)
    before, now = summary["before_labels"], summary["labels"]
    label_rows = "\n".join(
        f"| {name} | {before[key]:,} | {now[key]:,} |"
        for key, name in (("0", "Nhãn 0"), ("1", "Nhãn 1"), ("2", "Nhãn 2"), ("unlabeled", "Chưa nhãn"))
    )
    part_rows = "\n".join(
        f"| {p} (cũ) | {s['total']:,} | {s['labels']['0']} | {s['labels']['1']} | {s['labels']['2']} | {s['labels']['unlabeled']:,} |"
        for p, s in summary["partitions"].items()
    )
    transitions = "\n".join(f"| `{k}` | {v:,} |" for k, v in sorted(summary["transitions"].items()))
    cv_fn = "\n".join(f"| `{k}` | {v} |" for k, v in sorted(summary["task_coverage"]["functions_cv"].items()))
    jd_fn = "\n".join(f"| `{k}` | {v} |" for k, v in sorted(summary["task_coverage"]["functions_jd"].items()))
    first_ps = str(first).replace("/", "\\")
    doc = f"""# Đối chiếu nhiệm vụ có bằng chứng v4 — 17/11/2026

**Đã triển khai và chạy `task-evidence-proxy-v4` trên toàn bộ {summary['pair_count']:,} cặp ({summary['cv_count']} CV synthetic / {summary['jd_count']} JD) bằng Python chuẩn, không gọi LLM hay dịch vụ mạng.** Chức danh/tên nghề (`role`/`title`) chỉ còn là metadata hiển thị và thống kê phân bố; quyết định gán nhãn kiểm tra bất biến đổi tên chức danh trên cả {summary['title_ablation_checked_pairs']:,} cặp (`title_used_for_decision=false`).

[Receipt từ hai run](reports/20261117-task-matching-v4.json), [policy v4](data_configs/task_evidence_proxy_v4.json), [ví dụ chức danh mới đạt nhãn 2](examples/unseen_title_pair.json), [ví dụ trùng kỹ năng nhưng khác nhiệm vụ](examples/unknown_task_pair.json).

## 1. Quy tắc đối chiếu không phụ thuộc danh sách tên nghề

- **Loại bỏ cổng tên nghề:** Không so khớp chuỗi `cv.role == jd.role`, không dùng danh sách nghề đóng để cho qua hay chặn cặp, và không trích xuất kỹ năng từ tiêu đề công việc (`title_for_matching`).
- **Nhãn 0 (`{now['0']}` cặp):** Chỉ khi có mâu thuẫn rõ với điều kiện bắt buộc áp dụng được (phủ định kỹ năng bắt buộc hoặc số tháng kinh nghiệm `employment`/`contract` cùng scope thấp hơn ngưỡng bắt buộc). Khác tên nghề, khác nhiệm vụ hoặc thiếu nhắc tới kỹ năng không bị gán `0`.
- **Nhãn 1 (`{now['1']}` cặp):** Khi cả CV và JD đều có bằng chứng nhiệm vụ cùng họ công việc (`shared_functions`) **và** có công nghệ/kỹ năng chung trích từ nội dung chuyên môn (`shared_skills`), không rơi vào nhánh mâu thuẫn bắt buộc. Có **{summary['positive_pairs_with_unknown_jd_role']} cặp dương tính** trên các JD trước đây chưa xác định được `role`.
- **Nhãn 2 (`{now['2']}` cặp trong kho hiện tại):** Khi đạt điều kiện nhãn 1, mọi họ nhiệm vụ phát hiện ở JD đều được CV chứng minh, mọi đoạn nhiệm vụ JD đều nằm trong ngữ pháp đóng (`bounded_statement_complete`), toàn bộ phần yêu cầu JD thuộc ngữ pháp kỹ thuật đóng đã được giải thích (`complete_bounded_grammar`), và mọi điều kiện bắt buộc/thời lượng (nếu JD có nêu) đều đạt. **JD không nêu yêu cầu số năm không bị chặn nhãn 2** (đã kiểm chứng trên [unseen_title_pair.json](examples/unseen_title_pair.json)).
- **Trống (`{now['unlabeled']:,}` cặp):** Chưa đủ bằng chứng nhiệm vụ + kỹ năng chung (`{summary['blank_reasons']['insufficient_task_and_skill_evidence']:,}` cặp) hoặc giữ nguyên {summary['explicit_dataset_exclusions_preserved']} JD ngoài phạm vi phần mềm đã đánh dấu từ dataset trước (`{summary['blank_reasons']['preserved_dataset_scope_exclusion']:,}` cặp).

## 2. Kết quả trên 48.284 cặp và so sánh với v3

| Trạng thái | v3 | v4 |
|---|---:|---:|
{label_rows}

| Partition gốc — chỉ chẩn đoán | Cặp | 0 | 1 | 2 | Trống |
|---|---:|---:|---:|---:|---:|
{part_rows}

| Chuyển trạng thái v3 → v4 | Số cặp |
|---|---:|
{transitions}

Số nhãn `1` giảm từ `2,427` xuống `325` vì v3 cho phép gán nhãn `1` khi trùng tên nghề (`same_specific_occupation`) kèm kỹ năng chung dù chưa bắt được hành động nhiệm vụ trong văn bản; v4 bỏ hẳn điều kiện trùng tên nghề và bắt buộc bằng chứng nhiệm vụ (`action + object`) ở cả hai phía. Ngược lại, v4 mở khóa `164` cặp `unlabeled -> 1` và `9` cặp `unlabeled -> 0` (trong đó có các JD `role` rỗng mà v3 bỏ qua).

## 3. Độ phủ bộ đọc nhiệm vụ và yêu cầu trong v4

- **CV có bằng chứng nhiệm vụ theo mẫu `action + object`:** {summary['task_coverage']['cv_after']}/{summary['cv_count']} CV (v3: {summary['task_coverage']['cv_before']}/{summary['cv_count']}).
- **JD có bằng chứng nhiệm vụ theo mẫu `action + object`:** {summary['task_coverage']['jd_after']}/{summary['jd_count']} JD (v3: {summary['task_coverage']['jd_before']}/{summary['jd_count']}).
- **JD có toàn bộ đoạn yêu cầu nằm trọn trong ngữ pháp đóng (`jd_complete_bounded_requirements`):** {summary['jd_complete_bounded_requirements']}/{summary['jd_count']} JD.

| Họ nhiệm vụ CV (`functions_cv`) | Số CV |
|---|---:|
{cv_fn}

| Họ nhiệm vụ JD (`functions_jd`) | Số JD |
|---|---:|
{jd_fn}

## 4. Kiểm chứng và lệnh PowerShell

- Hai run `{first.as_posix()}` và `{second.as_posix()}` có **{len(maps[0])}/{len(maps[0])} file giống byte**.
- **{tests[1]} test đạt**, {float(tests[2]):.3f} giây (`tests/ml/test_task_matching.py` thêm 22 test mới kiểm tra chức danh chưa từng gặp, đổi tên chức danh bất biến, trùng công nghệ nhưng khác nhiệm vụ, ngữ cảnh phủ định/giả định/tương lai/giảng dạy, ưu tiên cuối câu và bảo toàn offset).
- Toàn bộ 120 CV vẫn giữ `effective_exposure=development`, `evaluation_eligible=false`; chưa huấn luyện model mới.

```powershell
Set-Location D:\\JobApply
$pythonML = '.\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe'
& $pythonML -m ml_task_matching check --artifact '.\\{first_ps}'
if ($LASTEXITCODE -ne 0) {{ throw 'Task matching v4 check failed' }}

$v4Out = '.\\ml_data_runs\\task_matching_v4_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_task_matching prepare --parent .\\ml_data_runs\\20261117_label_revision_v3_02 --output $v4Out
if ($LASTEXITCODE -ne 0) {{ throw 'Task matching v4 prepare failed' }}

$pairOut = '.\\ml_data_runs\\pair_inspect_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff') + '.json'
& $pythonML -m ml_task_matching inspect-pair --input .\\docs\\ml\\examples\\unseen_title_pair.json --output $pairOut
```
"""
    (folder / "task_matching_v4.md").write_text(doc, encoding="utf-8", newline="\n")
    print(dict(identical_files=len(maps[0]), tests=int(tests[1]), labels=now))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "log", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    main(args.first, args.second, args.log, args.output)
