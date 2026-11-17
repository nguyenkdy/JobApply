"""Generate aggregate handoff after a full inventory check and byte-identical repeat."""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, require, verify, write_json  # noqa: E402
from ml_readiness.__main__ import TYPE, check  # noqa: E402


def main(first, second, log, output):
    checked = check(first)
    verify(second, TYPE)
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], "Repeated inventory differs")
    summary = read_json(first / "summary.json")
    text = log.read_text(encoding="utf-16" if log.read_bytes().startswith(b"\xff\xfe") else "utf-8-sig")
    test = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+OK\s*$", text)
    require(test, "Complete successful test log required")
    folder = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(summary=summary, check=checked, identical_files=len(maps[0]), first=first.as_posix(), repeat=second.as_posix(),
        manifest_sha256=file_hash(first / "manifest.json"), tests=dict(passed=int(test[1]), seconds=float(test[2]), log_sha256=file_hash(log)),
        proposed_rubric=dict(path="docs/ml/recommendation_label_contract.md", sha256=file_hash(ROOT / "docs/ml/recommendation_label_contract.md"), applied=False))
    write_json(folder / "20261117-document-inventory.json", receipt)
    names = dict(source_field_empty="Trường nguồn rỗng", source_explicitly_leaves_timeline_unknown="CV nói rõ thời gian chưa xác nhận, không có cue thời lượng số",
        partial_extraction_with_unresolved_cues="Có thời lượng đã đọc và còn cue chưa phân giải",
        numeric_cue_without_parsed_scope="Có cue thời lượng số nhưng chưa đọc được scope",
        parsed_evidence_present_not_semantic_certification="Có evidence thời lượng, không còn cue số chưa giải thích",
        numeric_cues_only_optional_or_unclassified="Cue số chỉ được giải thích là ưu tiên/khác",
        no_numeric_cue_detected_absence_not_proven="Không phát hiện cue số; chưa chứng minh thiếu thông tin")
    table = "\n".join(f"| {kind.upper()} | {names[state]} | {count} |" for kind in ("cv", "jd") for state, count in summary["by_kind"][kind]["duration_status"].items())
    cv, jd = summary["by_kind"]["cv"], summary["by_kind"]["jd"]
    path = str(first).replace("/", "\\")
    doc = f"""# Rà định nghĩa nhãn và kiểm kê hồ sơ — 17/11/2026

**Đã hoàn tất lượt rà quy tắc và kiểm kê {summary['records']} hồ sơ: 120 CV / 788 JD. Không đổi nhãn, không sửa parser, không train.**

[Định nghĩa nhãn đề xuất, chưa áp dụng](recommendation_label_contract.md), [receipt từ run](reports/20261117-document-inventory.json), [nhãn v3 giữ nguyên](label_revision_v3.md).

## 1. Kết luận về định nghĩa nhãn

Tài liệu 14/11 từng dùng khác nghề làm nhãn 0; luật v3 không làm vậy. Đã đánh dấu tài liệu cũ là lịch sử để tránh dùng nhầm. Định nghĩa đề xuất dùng bằng chứng nhiệm vụ và điều kiện chuyên môn, không dùng title mismatch; chưa triển khai nhánh “không tương thích nhiệm vụ”.

Luật v3 bắt buộc có thời lượng và điều kiện công nghệ đã đọc mới cho nhãn 2. Đây là chốt chặn của luật, không phải yêu cầu mọi JD thực tế đều có. Hợp đồng đề xuất bỏ việc tự thêm yêu cầu thời lượng vào JD, nhưng chỉ sau khi kiểm đủ phần yêu cầu để phân biệt “không yêu cầu” với “chưa đọc được”. **Không có nhãn mới nào từ hợp đồng này.**

## 2. Kiểm kê có bằng chứng, không đánh đồng cue với sự thật

Mỗi hồ sơ có hàng trong `record_inventory.csv`; `field_evidence.jsonl` lưu quote, field, offset và hash liên kết nguồn. Tool đọc nguyên văn cùng facts v3. Cue số/tháng/năm, từ chỉ hành động hoặc tên công nghệ chỉ là tín hiệu để điều tra; có thể thuộc ưu tiên, phủ định hoặc ngữ cảnh không phải yêu cầu. Không dùng chúng để tự sinh nhãn.

| Loại | Trạng thái thời lượng — loại trừ nhau trong mỗi loại | Hồ sơ |
|---|---|---:|
{table}

Ở CV: **{summary['cv_duration']['no_duration']} hồ sơ chưa có duration fact**, **{summary['cv_duration']['employment_or_contract']} có thời lượng employment/contract**, chỉ **{summary['cv_duration']['specific_employment_scope']} có scope nghề/công nghệ cụ thể trong loại kinh nghiệm đó**. Không tự sửa CV hoặc điền số tháng từ tổng năm. Các câu nói rõ thiếu nhật ký/thời gian là bằng chứng nguồn chưa đủ, không phải việc parser chưa nhận được chữ số.

Ở JD: cả **{jd['requirements_nonempty']} hồ sơ có trường yêu cầu**, **{jd['tasks_nonempty']} có trường nhiệm vụ**. **{jd['preferred_field_empty']} trường ưu tiên rỗng** không đồng nghĩa không có ưu tiên: nội dung có thể nằm trong yêu cầu. Facts có nghề ở {jd['role_parsed']} JD; số còn lại chưa được parser xác định, không khẳng định chức danh nguồn rỗng.

## 3. Công việc cần ưu tiên cho bộ đọc

- **{cv['action_cues_without_task_function']} CV và {jd['action_cues_without_task_function']} JD** có cue hành động nhưng chưa có task function. Đây là hàng đợi kiểm khả năng đọc nhiệm vụ; không chứng minh toàn bộ là lỗi parser hoặc các CV/JD này phù hợp nhau.
- **{jd['technology_cues_without_positive_skill']} JD** có tên công nghệ nhưng không có positive skill fact. Cần phân biệt ưu tiên/phủ định/ngữ cảnh; không tự chuyển tất cả thành kỹ năng bắt buộc.
- **{jd['records_with_unresolved_clauses']} JD** còn mệnh đề unresolved. Chưa có cơ sở khẳng định đọc đủ yêu cầu để cấp nhãn 2.
- `extraction_probe_set.jsonl` lấy tối đa năm ID đầu theo mỗi nhóm loại hồ sơ/trạng thái thời lượng để phát triển công cụ. Không dùng nhãn hay ranking để chọn; **không đại diện ngẫu nhiên, không phải test độc lập**, không đo accuracy từ tập này.

Đây là kiểm kê kỹ thuật có phân biệt mức chắc chắn, **chưa phải kiểm đầy đủ ngữ nghĩa của mọi câu**. Không thể khẳng định toàn bộ phần còn thiếu là lỗi regex hay nguồn thiếu. Những trường hợp không có cue số nhưng có thể diễn đạt bằng chữ hoặc có điều kiện ngầm vẫn cần kiểm riêng.

## 4. Việc tiếp theo đã được xác định, chưa thực hiện

1. Từ các hàng đợi trên, xây các tình huống kiểm trích xuất nhiệm vụ, bắt buộc/ưu tiên, AND/OR và thời lượng theo scope. Giữ nguồn và offset, tách kết quả parse khỏi kết luận relevance.
2. So phương án regex hiện tại với phương án đọc có cấu trúc; nếu thử LLM phải khóa model/prompt/schema, lưu đầu ra và kiểm evidence. Chưa chọn LLM/nhà cung cấp, chưa gửi CV/JD ra ngoài, chưa phát sinh chi phí API.
3. Chỉ triển khai định nghĩa nhãn đề xuất khi có cách xác định đủ nhiệm vụ/yêu cầu và các tình huống đối chứng đạt. Không ép đủ lớp bằng title mismatch hoặc biến missing thành 0.
4. Sau khi phương pháp ổn định, mới chuẩn bị dữ liệu đánh giá mới. Cả 120 CV hiện tại vẫn development, không đổi seed/lineage. Data Analyst vẫn là mục tiêu nghiên cứu và cần nguồn JD đủ điều kiện riêng.

## 5. Kiểm chứng và lệnh PowerShell

Hai run `{first.as_posix()}` và `{second.as_posix()}` có **{len(maps[0])}/{len(maps[0])} file giống byte**. Run đầu được dựng lại toàn bộ inventory/evidence và kiểm chain v3; run lặp kiểm manifest rồi đối chiếu nguyên byte. **{test[1]} test đạt**, {float(test[2]):.3f} giây. Nguồn/pilot, nhãn v3, CV/JD và partition giữ nguyên. Không thay API/UI/Docker/VM.

Code mới nằm riêng `ml_readiness/` để không đổi fingerprint của parser/luật đã đóng băng. Test: `tests/ml/test_document_inventory.py`; script sinh báo cáo: `scripts/report-document-inventory.py`.

```powershell
Set-Location D:\\JobApply
$pythonML = '.\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe'
& $pythonML -m ml_readiness check --artifact '.\\{path}'
if ($LASTEXITCODE -ne 0) {{ throw 'Inventory check failed' }}

$auditOut = '.\\ml_data_runs\\document_inventory_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_readiness prepare --parent .\\ml_data_runs\\20261117_label_revision_v3_02 --output $auditOut
if ($LASTEXITCODE -ne 0) {{ throw 'Inventory failed' }}
```
"""
    (folder / "document_inventory.md").write_text(doc, encoding="utf-8", newline="\n")
    print(dict(identical_files=len(maps[0]), tests=int(test[1]), records=summary["records"], new_labels=0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "log", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    main(args.first, args.second, args.log, args.output)
