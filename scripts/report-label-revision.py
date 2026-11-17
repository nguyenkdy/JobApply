"""Check paired development-label runs and generate a factual handoff. No model fitting."""
import argparse
from collections import Counter
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, read_lines, require, write_json  # noqa: E402
from ml_data.label_revision import check_revision  # noqa: E402


def report(first, second, tests_log, output):
    first, second = Path(first), Path(second)
    checks = [check_revision(p) for p in (first, second)]
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], "Repeated revision runs differ")
    log = Path(tests_log)
    text = log.read_text(encoding="utf-16" if log.read_bytes().startswith(b"\xff\xfe") else "utf-8-sig")
    test = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+OK\s*$", text)
    require(test, "Complete successful test result not found")
    summary = read_json(first / "summary.json")
    inputs = read_json(first / "input_receipt.json")
    previous = read_json(ROOT / inputs["old_labels_path"] / "summary.json")
    before_parser = read_json(ROOT / inputs["old_labels_path"] / "parsing_coverage.json")
    evidence = read_lines(first / "evidence.jsonl")
    negatives = dict(Counter("duration" if any(s["state"] == "no" for s in r["duration_states"]) else "technology"
                             for r in evidence if r["relevance_0_1_2"] == "0"))
    task_partial = sum(r["relation"] == "shared_task_function" and r["relevance_0_1_2"] == "1" for r in evidence)
    contract = read_json(first / "input_contract.json")
    folder = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(summary=summary, before_labels=previous["labels"], before_parser=before_parser,
        verification=dict(checks=checks, files_identical=len(maps[0]), manifest_sha256=file_hash(first / "manifest.json")),
        tests=dict(passed=int(test[1]), seconds=float(test[2]), log_sha256=file_hash(log)),
        negative_causes=negatives, task_supported_label_one=task_partial,
        input_contract=dict(version=contract["version"], entries=len(contract["entries"]),
                            accepted_as=dict(Counter(r["accepted_as"] for r in contract["entries"]))),
        runs=dict(first=first.as_posix(), repeat=second.as_posix()))
    write_json(folder / "20261117-label-revision-v2.json", receipt)
    write_json(folder / "technical_proxy_v2.json", read_json(first / "policy.json"))
    table = "\n".join(f"| {p} (cũ) | {summary['partitions'][p]['total']:,} | " + " | ".join(
        str(summary["partitions"][p]["labels"].get(k, 0)) for k in ("0", "1", "2", "unlabeled")) + " |" for p in ("train", "validation", "test"))
    changes = "\n".join(f"| `{key}` | {value:,} |" for key, value in summary["transitions"].items())
    script_first = first.as_posix().replace("/", "\\")
    doc = f"""# Quy tắc kỹ thuật v2 và chấm lại development — 17/11/2026

**Đã triển khai phiên bản kiểm tra đầu vào và bộ luật mới, chạy đủ {summary['pair_count']:,} cặp hai lần, chưa train.** Lô vẫn là 120 CV synthetic và 788 JD. Kết quả thực tế: **{summary['labels'].get('0', 0)} nhãn 0, {summary['labels'].get('1', 0):,} nhãn 1, {summary['labels'].get('2', 0)} nhãn 2, {summary['labels'].get('unlabeled', 0):,} cặp chưa nhãn**. Đây chưa phải dataset sẵn sàng cho thí nghiệm xếp hạng ba mức.

[Receipt sinh từ run](reports/20261117-label-revision-v2.json), [định nghĩa chính sách](data_configs/technical_proxy_v2.json), [audit dẫn đến thay đổi này](readiness_audit.md).

## Giữ dữ liệu và sửa kiểm tra đầu vào

`protected-input-contract-v2` giữ hash lịch sử và liên kết tới manifest audit. {receipt['input_contract']['accepted_as'].get('exact_historical_bytes', 0)} file vẫn phải khớp nguyên byte; chỉ {receipt['input_contract']['accepted_as'].get('audited_code_lf_equivalence', 0)} đường dẫn mã/lock có chứng cứ CRLF/LF được chấp nhận theo nội dung LF chuẩn đã kiểm. Thay mã, đổi dependency hoặc đổi newline CSV vẫn bị từ chối. Không ghi đè receipt cũ, không sửa gate strict của lệnh v1.

Mã thực thi v2 lưu cả hash raw và hash LF, cùng snapshot `tool_source/`. Checker so snapshot với fingerprint đã khai và nội dung LF của code hiện tại; khác nội dung thực thi bị chặn. Python/platform/Unicode được ghi trong `runtime.json`; pipeline này chỉ dùng thư viện chuẩn, không tải/chạy encoder.

CV/JD, lineage, ID, partition, seed, file nguồn và nhãn v1 giữ nguyên. V2 tạo facts/nhãn ở artifact riêng, liên kết manifest các đầu vào. Không nhập JD vào database app, không đổi API/UI/Docker/VM.

## Luật đã thay đổi những gì?

- Đọc nhiều cách viết yêu cầu tiếng Việt/Anh; phân biệt phần ưu tiên, yêu cầu trộn ưu tiên và điều kiện theo cấp độ. Phần không đọc hết vẫn unresolved.
- Có cây AND/OR giữ ngoặc: `(Python hoặc Java) và SQL` khác `Python hoặc Java và SQL`. Danh sách dấu phẩy/slash đơn thuần vẫn chưa được tự coi là AND/OR.
- Chuẩn hóa alias cụ thể như Postgres/PostgreSQL, ReactJS/React; vẫn tách Java/JavaScript, React/React Native, .NET/ASP.NET Core.
- Đọc ngưỡng tháng/năm, dấu cộng và số thập phân, giữ scope nghề/công nghệ. Khoảng năm giữ cận trên chưa rõ cách diễn giải, không dùng để khẳng định nhãn 2. Tổng kinh nghiệm không biến thành thời gian từng công nghệ; dự án/thực tập không thay thời gian nghề nghiệp.
- Cùng nghề cụ thể và có công nghệ chung vẫn có thể nhận nhãn 1. Khi khác nghề, cần **bằng chứng nhiệm vụ chung trong văn bản** cùng kỹ năng chung; không chỉ dùng một nhóm nghề rộng. Có {task_partial} nhãn 1 được hỗ trợ theo nhánh nhiệm vụ chung này. Không suy không phù hợp chỉ từ khác chức danh hoặc thiếu skill trong CV.
- Nhãn 0 chỉ dựa trên mâu thuẫn điều kiện bắt buộc rõ ràng. Trong run thực, {negatives.get('duration', 0)} nhãn 0 đến từ thời lượng cùng scope không đạt; {negatives.get('technology', 0)} đến từ phủ định công nghệ. “Chưa quản trị Kubernetes” không bị đổi thành “chưa từng dùng Kubernetes”.

Luật v2 vẫn là **proxy kỹ thuật**, không chứng nhận phù hợp tuyển dụng, chưa đánh giá đầy đủ học vấn/ngoại ngữ/kỹ năng mềm. Cây logic có test không có nghĩa đã hiểu hết văn bản tự nhiên.

## Độ phủ parser thực tế

| Chỉ số JD | v1 | v2 |
|---|---:|---:|
| Có mệnh đề công nghệ bắt buộc đọc được đầy đủ | {before_parser['jd_with_mandatory_technology']} | {summary['parser']['jd_with_mandatory_technology']} |
| Có thời lượng và scope được parser chấp nhận | {before_parser['jd_with_parsed_duration']} | {summary['parser']['jd_with_parsed_duration']} |

Overlay nghề thay đổi {summary['parser']['occupation_overlay_changes']} JD theo cụm chức danh rõ, số JD role rỗng còn {summary['parser']['empty_role_after_overlay']}. Có {summary['parser']['generic_role_after_overlay']} nghề còn generic, {summary['parser']['outside_software_scope']} JD ngoài phạm vi phần mềm theo v2 (vẫn giữ trong catalog). Một chức danh Curriculum Developer được nhận diện là Education/Training; không đổi dữ liệu nguồn để loại khỏi kho.

Phát hiện bằng chứng nhiệm vụ theo ngữ pháp hiện tại ở {summary['parser']['jd_with_task_evidence']}/788 JD và {summary['parser']['cv_with_task_evidence']}/120 CV. Số còn lại không có nghĩa không có nhiệm vụ: cách đọc vẫn hẹp và CV synthetic có cách diễn đạt ngắn, tương tự nhau. Còn {summary['parser']['clause_states'].get('unresolved', 0):,} mệnh đề unresolved trong phạm vi câu v2 xem xét; phạm vi này rộng hơn v1 nên không so hai số unresolved như cùng một mẫu.

## Nhãn thay đổi ra sao?

| Nhóm partition gốc — chỉ để chẩn đoán | Số cặp | Nhãn 0 | Nhãn 1 | Nhãn 2 | Trống |
|---|---:|---:|---:|---:|---:|
{table}

| Chuyển nhãn v1 → v2 | Số cặp |
|---|---:|
{changes}

Số nhãn giảm so với v1 chủ yếu vì luật v1 cho phép các nghề thuộc một nhóm rộng nhận nhãn 1 khi trùng công nghệ; v2 yêu cầu bằng chứng nhiệm vụ nếu nghề khác nhau. **Không gọi việc giảm/tăng nhãn là tăng độ chính xác.** Không có đánh giá độc lập chứng minh nhãn v2 đúng hơn. Việc mở rộng parser và siết tiền đề tương thích là hai thay đổi khác nhau.

## Exposure: không còn gọi validation/test cũ là holdout độc lập

Lần sửa chính sách này bắt nguồn từ audit của toàn bộ lô, có cả validation/test. Vì vậy `exposure_overlay.json` đánh dấu **cả 120 CV / 12 nhóm là development**, `evaluation_eligible=false`, không có CV test độc lập còn lại cho chính sách mới.

Không đổi hoặc xóa partition gốc: `source_assignments.jsonl` giống byte file intake, cột `partition` trong nhãn chỉ giữ tên nhóm cũ để đối chiếu. **Không dùng tên cột đó để coi các cặp là holdout mới.** Mọi dòng có `effective_exposure=development`; artifact có loại `development-label-revision`, không phải đầu vào pretraining-ready. Không đổi seed, bẻ nhóm hoặc sửa lineage để tạo độc lập giả.

## Kiểm chứng và nơi xem

- Run chính `{first.as_posix()}`; lặp `{second.as_posix()}`: **{len(maps[0])}/{len(maps[0])} file giống byte**.
- **{test[1]} test đạt**, {float(test[2]):.3f} giây. Test mới bao gồm scope, range, logic ngoặc, ưu tiên/điều kiện, task evidence, phủ định, checksum và exposure cả nhóm. Các test dùng fixture riêng.
- Checker tái dựng facts từ input, kiểm offset, áp lại policy cho toàn bộ cặp, đối chiếu CSV/evidence/tổng hợp/lineage/partition/exposure. Input contract kiểm nguồn và chứng cứ newline.
- `labels.csv`, `evidence.jsonl`: quyết định từng cặp và căn cứ; `cv_facts.json`, `jd_facts.json`: phần trích xuất; `summary.json`: phân bố và thay đổi so với v1.
- `input_contract.json`, `input_receipt.json`, `execution_fingerprints.json`, `runtime.json`, `manifest.json`: provenance, môi trường và kiểm toàn vẹn.

```powershell
Set-Location D:\\JobApply
$pythonML = '.\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe'
& $pythonML -m ml_data check-label-revision --artifact '.\\{script_first}'
if ($LASTEXITCODE -ne 0) {{ throw 'Label revision check failed' }}

$revisionOut = '.\\ml_data_runs\\label_revision_v2_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_data prepare-label-revision --intake .\\ml_data_runs\\20261116_authored_cv_v7_01 --old-labels .\\ml_data_runs\\20261116_expanded_labels_v1_01 --audit .\\ml_data_runs\\20261116_readiness_audit_v1_01 --output $revisionOut
if ($LASTEXITCODE -ne 0) {{ throw 'Label revision failed' }}
```

## Điều kiện còn thiếu — chưa huấn luyện

Nhóm train gốc chỉ có {summary['partitions']['train']['labels'].get('0', 0)} nhãn 0, {summary['partitions']['train']['labels'].get('1', 0)} nhãn 1 và {summary['partitions']['train']['labels'].get('2', 0)} nhãn 2. Hai lớp cho phép một số thuật toán chạy về mặt kỹ thuật, nhưng dữ liệu này **chưa đáp ứng mục tiêu thí nghiệm relevance 0/1/2** và không còn holdout độc lập. Không train, không chọn model, không đo Recall@5/NDCG@5 từ các ô trống.

Tiếp theo cần kiểm chứng ngữ nghĩa và mở rộng các cấu trúc yêu cầu còn chưa hiểu trên development; hoàn thiện bằng chứng theo scope của CV mà không viết CV để khớp JD đích. Sau khi khóa phương pháp, mới chuẩn bị nhóm CV đánh giá mới có nguồn/lineage độc lập phù hợp. Không tăng số CV để che thiếu nhãn hoặc tự gọi nhãn do luật tạo là gold. Data Analyst vẫn cần JD đủ điều kiện cho benchmark; không bị thay bằng Data Engineer.
"""
    (folder / "label_revision_v2.md").write_text(doc, encoding="utf-8", newline="\n")
    print(dict(files_identical=len(maps[0]), tests=int(test[1]), labels=summary["labels"], ready_for_training=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("first", "second", "tests-log", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    report(args.first, args.second, args.tests_log, args.output)
