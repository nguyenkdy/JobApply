"""Build a public metadata-only receipt from two verified, reproducible upstream runs."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, require, verify, write_json


def build(first, second, output):
    first, second = Path(first).resolve(), Path(second).resolve()
    for folder in (first, second):
        verify(folder, "upstream")
        verify(folder / "dataset", "dataset")
    hashes = [{p.relative_to(folder).as_posix(): file_hash(p) for p in folder.rglob("*") if p.is_file()}
              for folder in (first, second)]
    require(hashes[0] == hashes[1], "Runs differ; do not publish a reproducibility claim")
    summary = read_json(first / "summary.json")
    for name, expected in summary["source_hashes"].items():
        require(file_hash(ROOT / name) == expected, "Original upstream bytes changed: " + name)
    baseline = ROOT / "jobapply_pilot_v1/results/reruns/20261112_baseline_03"
    before = read_json(baseline / "manifest.json")
    originals = {name: info["sha256"] for name, info in before["artifacts"].items() if name.startswith("inputs/")}
    for name, expected in originals.items():
        require(file_hash(ROOT / "jobapply_pilot_v1" / name.removeprefix("inputs/")) == expected, "Pilot original changed: " + name)
    report = dict(date="2026-11-13", scope="upstream v2 corrected status/length gates; no new CVs, formal splits, labels or training",
                  verification=dict(run_paths=[p.relative_to(ROOT).as_posix() for p in (first, second)],
                                    manifest_sha256=file_hash(first / "manifest.json"), all_files_identical=True,
                                    files_compared=len(hashes[0]), three_source_files_unchanged=True,
                                    pilot_original_files_checked=len(originals), pilot_original_files_unchanged=True),
                  **summary)
    folder = fresh_folder(output, (first, second))
    write_json(folder / "20261113-data-preparation.json", report)
    write_json(folder / "20261113-upstream-jd-selection.json", read_json(first / "selection.json"))
    config = read_json(first / "import_config.json")
    # This exported config will live in docs/ml/data_configs, not beside canonical_jd.csv.
    prefix = "../../../" + first.relative_to(ROOT).as_posix() + "/"
    for source in config["sources"]:
        source["path"] = prefix + source["path"]
    for source in config["context_files"]:
        source["path"] = prefix + source["path"]
    write_json(folder / "upstream_jd_import.json", config)
    p = summary["profiles"]
    rel = summary["relations"]
    decisions = summary["import_summary"]["distribution"]["jd"]["decisions"]
    batch = summary["batch"]
    analyst = summary["data_analyst_accounting"]
    source_table = "\n".join(f"| `{name}` | {x['records']} | {len(x['fields'])} | {x['invalid_utf8_rows']} | {x['replacement_character_rows']} |"
                             for name, x in p.items())
    duplicate_table = "\n".join(f"| `{name}` | {x['exact_text_duplicate_excess']} | {x['normalized_text_duplicate_excess']} | {x['near_pairs_between_unique_texts']} |"
                                for name, x in p.items())
    role_table = "\n".join(f"| {role} | {batch['available'][role]['records']} | {batch['available'][role]['groups']} | {batch['available'][role]['gate_passing']} | {count} |"
                           for role, count in batch["actual_by_role"].items())
    analyst_ids = ", ".join("`" + row["job_id"] + "`" for row in analyst["rows"] if row["selected"])
    reasons = "\n".join(f"- `{reason}`: {count}." for reason, count in summary["quality_reason_counts"].items())
    md = f"""# Mốc 2 — Kết quả upstream sau sửa điều kiện v2

Ngày 13/11/2026. Báo cáo được sinh từ hai run đã kiểm checksum và so sánh **{len(hashes[0])} file giống byte**. Không lấy lại số liệu/ID từ bản báo cáo v1. [Receipt đầy đủ](reports/20261113-data-preparation.json), [danh sách JD](reports/20261113-upstream-jd-selection.json), [schema cột thực tế](schemas/upstream_columns.json).

## 1. Ba file thực tế và quan hệ

| File | Record | Cột | Dòng có byte UTF-8 lỗi | Dòng có U+FFFD |
|---|---:|---:|---:|---:|
{source_table}

Raw chưa có `job_id`; dùng số thứ tự record CSV và URL/site để đối chiếu. Clean và matching là UTF-8 BOM hợp lệ, mỗi file có 3.062 ID duy nhất. Raw không phải UTF-8 hợp lệ; parser dùng `surrogateescape` chỉ để giữ cấu trúc CSV và byte lỗi, không phục hồi chữ đã mất. Không giải thích clean là kết quả sửa thành công từ chính bản raw hỏng hiện có.

- Raw → clean: {rel['raw_to_clean']['referenced_raw_rows']} tham chiếu khớp số dòng/URL/site; {rel['raw_to_clean']['primary_raw_rows']} dòng chính và {rel['raw_to_clean']['merged_nonprimary_rows']} dòng phụ được khai báo gộp. Dòng {rel['raw_to_clean']['unlinked_raw_rows']} không được tham chiếu, mô tả dài 12 ký tự. Đó là quan sát; lý do/thao tác lịch sử chưa có script chứng minh.
- Clean → matching: cùng {rel['clean_to_matching']['common_ids']} ID, không thêm/mất ID; {rel['clean_to_matching']['verified_description_hashes']} hash mô tả khớp. ID lệch là `job_906e26bf2136f879aba5`, mô tả clean chứa `#NAME?`. Có {rel['clean_to_matching']['common_field_changes']} dòng thay đổi ít nhất một trường chung; không mặc định nguyên nhân thay đổi.
- Matching → pilot: {rel['matching_to_pilot']['found']}/50 ID và {rel['matching_to_pilot']['pre_edit_hash_verified']}/50 hash trước chỉnh sửa khớp; {rel['matching_to_pilot']['changed_match_text']} văn bản pilot khác matching. `prepare_pilot.py` và nhật ký pilot có trong repo; chưa tìm được script/notebook tạo hai giai đoạn clean/matching trong phạm vi workspace đã kiểm kê. Chưa tái tạo lịch sử.

Ba CSV là ba giai đoạn cùng kho, chỉ import **matching một lần**, giữ raw/clean làm context snapshots. Số lượng 3.101 → 3.062 → 3.062 khớp lịch sử, nhưng không đủ chứng minh nguyên vẹn nội dung.

| File | Bản dư trùng text nguyên văn | Bản dư trùng sau chuẩn hóa | Cặp gần trùng giữa text duy nhất |
|---|---:|---:|---:|
{duplicate_table}

Near duplicate dùng Jaccard shingle 3 token ≥0,85, có thể nối bắc cầu; không phải chứng nhận tương đương ngữ nghĩa. Kết quả raw hỏng chỉ là chẩn đoán. Checksum, độ lớn, phân bố nguồn, thiếu dữ liệu và lỗi từng cột nằm trong receipt. Source revision/ngày thu thập/quyền phân phối chưa rõ; `pipeline_version=1.0.0` là chuỗi trong CSV, không phải script đã khôi phục.

## 2. Điều kiện đã sửa và kết quả import

Quy tắc **`{summary['version']}`**: chỉ qua gate khi `extraction_status=sections_found` **và** `needs_review=false` **và** `review_flags_json=[]`. Trạng thái boolean phải đọc được; `human_reviewed` không được biến thành xác nhận nhãn. Nguồn thực tế toàn bộ `human_reviewed=FALSE`. Tên trạng thái `ok` trong tài liệu cũ là sai.

Một hằng số chung **{summary['quality_policy']['minimum_body_chars']} ký tự sau NFKC/chuẩn hóa khoảng trắng** áp cho text chính của importer và ba trường `tasks_text`, `requirements_text`, `match_text` ở gate upstream. Chức danh và mục ưu tiên không chịu ngưỡng tối thiểu này. Lỗi bảng tính, ký tự thay thế, hash/identity không kiểm chứng được vẫn bị cách ly dù cờ nguồn ghi FALSE. Ngưỡng là quy tắc kiểm tra kỹ thuật, không chứng minh đủ nội dung chuyên môn.

| Quyết định | JD | Ý nghĩa |
|---|---:|---|
| `keep` | {decisions['keep']} | Qua gate kỹ thuật; chưa có nhãn CV–JD hay xác nhận chuyên gia |
| `exclude_exact_duplicate` | {decisions['exclude_exact_duplicate']} | Bản dư cùng text chuẩn hóa với một bản keep; vẫn giữ raw/provenance |
| `quarantine` | {decisions['quarantine']} | Cần rà nguồn/parser, không đưa vào split hoặc huấn luyện |

Trong keep, **{summary['decisions_by_exposure']['True']['keep']} development** và **{summary['decisions_by_exposure']['False']['keep']} prospective**. Prospective chỉ là ứng viên cho bước sau, chưa phải train/test sẵn sàng. Tổng {summary['import_summary']['groups']} nhóm; {summary['pilot_related_records_before_selection']} record nối với pilot đã bị giữ development trước khi chọn lô mới.

Lý do cách ly có thể chồng nhau, **không cộng các số dưới thành tổng JD**:

{reasons}

Các ô `#NAME?` là lỗi quan sát được; chưa xác minh phần mềm hoặc thao tác nào gây ra. Không tự tái tạo đoạn bị mất. `match_text` gốc không bị sửa. Skills/stack/scoped experience chưa kiểm chứng giữ rỗng/unknown, không biến thành 0 tháng. Dấu hiệu nghề, số năm/tháng, từ bắt buộc và từ khóa chỉ phục vụ lấy mẫu, lưu rule version cùng trường/offset/trích đoạn; không phải bộ trích xuất kinh nghiệm đúng scope.

## 3. Lô development và Data Analyst

Đã chọn **{batch['total']} JD** ngoài các nhóm pilot: **{batch['gate_decisions'].get('keep', 0)} keep và {batch['gate_decisions'].get('quarantine', 0)} quarantine để rà parser**. Mục tiêu 12/nhóm; một JD mỗi group. Quarantine trong lô không phải JD huấn luyện. Lô có {batch['vietnamese_signal']} JD có dấu hiệu tiếng Việt, {batch['experience_mentions']} có nhắc thời lượng, {batch['must_mentions']} có từ chỉ điều kiện bắt buộc và {batch['preferred_present']} có mục ưu tiên; đều là dấu hiệu văn bản, chưa xác minh nghĩa.

| Nhóm lấy mẫu | Record ứng viên ngoài pilot | Group ứng viên | Record qua gate | Đã chọn |
|---|---:|---:|---:|---:|
{role_table}

Không cộng cột ứng viên giữa nghề như các mẫu độc lập vì một JD có thể có nhiều dấu hiệu. Seed `{batch['seed']}`; ưu tiên keep, dấu hiệu tiếng Việt, đa dạng biểu thức kinh nghiệm/ưu tiên và tie-break xác định. Mọi ID, lý do, evidence và quyết định được lưu trong danh sách JSON.

**Data Analyst:** nguồn clean gắn tag cho {analyst['source_tagged']} JD; quy tắc chức danh nhận {analyst['title_cued']} JD, gồm `Data Analytics Specialist`. Có {analyst['source_only']} JD chỉ mang tag nguồn (`Analytics Engineer`), chưa tự coi là cùng nhiệm vụ để đủ quota. Có {analyst['pilot_related']} JD thuộc pilot, còn **{analyst['nonpilot_gate_passing']} JD ngoài pilot qua gate** trong nhóm kiểm kê này. Chọn {analyst['selected']} trường hợp để sửa parser, thiếu {batch['shortages'].get('Data Analyst', 0)} so với mục tiêu 12. Không kết luận toàn thị trường/kho chỉ có từng ấy Data Analyst; quy tắc tên nghề còn có giới hạn.

ID Data Analyst thực chọn: {analyst_ids}.

Lô mới và closure nhóm chứa {batch['development_group_closure']} record development ngoài nhóm pilot. Chưa tạo CV mới, cặp nhãn hay khóa split trong hai run v2. Không dùng preview split cũ làm split chính thức. Chưa train lại, chưa chấm hai reviewer, không nhập JD lịch sử vào database app hoặc đổi API/UI/Docker/VM.

## 4. CV mới và bước tiếp theo

Chỉ dùng số liệu v2 đã xác nhận để định cỡ lô CV. Cần rà/khôi phục hoặc bổ sung JD Data Analyst trước khi kỳ vọng benchmark sáu nhóm cân đối. Trước mắt có thể thiết kế CV độc lập cho năm nhóm có JD qua gate; CV Data Analyst phục vụ parser phải ghi development, không dùng quota giả để tuyên bố đủ test.

CSV CV đề xuất, một dòng/tài liệu, mapping trong config:

| Cột | Ý nghĩa |
|---|---|
| `cv_id`, `cv_text` | ID ổn định và text chuyên môn đã ẩn danh, tối thiểu 80 ký tự chuẩn hóa |
| `source_group` | Cùng hồ sơ/người/tài liệu gốc dùng cùng mã qua mọi biến thể |
| `template_group` | Bắt buộc cho synthetic; cùng khung/generator family không tách partition |
| `is_synthetic` | `true`/`false` tường minh; CV tạo mới luôn synthetic |
| `role`, `skills`, `stack` | Metadata có căn cứ; skills/stack phân tách `;`, không biết để trống |
| `experience_json` | JSON scope → tháng có bằng chứng; thiếu giữ `{{}}`/trống, không suy từ tuổi/skill liệt kê |
| `exposure`, `text_scope` | development nếu đã dùng chỉnh phương pháp; prospective nếu ứng viên chia tập. `professional` sau khi đã rà text, mặc định unreviewed cách ly |

Tạo nguồn CV có version/manifest và quyền sử dụng; gom lineage trước, rà phân bố và chọn protocol `known-jd` hoặc `new-both` khi đã có CV đủ độc lập. Không mặc định ghép mọi CV với JD không được chọn là nhãn 0. [Config template](data_configs/new_cvs.template.json) chưa chứa CV thực tế.

## 5. PowerShell tái tạo và sinh báo cáo

Các output lớn, nguồn và text đầy đủ nằm trong `ml_data_runs/` đã Git ignore; chỉ schema/config/receipt được giữ trong repo. Ba nguồn local cần đi kèm khi tái tạo. [Config export hiện hành](data_configs/upstream_jd_import.json) trỏ tới canonical/context của run v2 local, không dùng được chỉ bằng clone mà thiếu run.

```powershell
Set-Location D:\\JobApply
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$base = ".\\ml_data_runs\\$runId"
python -m ml_data upstream --source-dir . --output "$base\\first" --seed 20261113
if ($LASTEXITCODE -ne 0) {{ throw 'First upstream run failed' }}
python -m ml_data upstream --source-dir . --output "$base\\second" --seed 20261113
if ($LASTEXITCODE -ne 0) {{ throw 'Second upstream run failed' }}
python .\\scripts\\report-upstream.py --first "$base\\first" --second "$base\\second" --output "$base\\reports"
if ($LASTEXITCODE -ne 0) {{ throw 'Reproducibility or original-file check failed' }}
python -m ml_data verify --artifact "$base\\first\\dataset"
```

Script report chỉ tạo output mới, xác minh nguồn/pilot và mọi hash trước khi xuất báo cáo. Không có lệnh tạo split ở lượt này. Chạy test:

```powershell
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m unittest discover -s tests/ml -v
& .\\.venv\\Scripts\\python.exe -m ruff check ml_data scripts/report-upstream.py tests/ml/test_upstream.py
```
"""
    (folder / "dataset_pipeline.md").write_text(md, encoding="utf-8", newline="\n")
    print(f"Verified {len(hashes[0])} identical files, three upstream sources and {len(originals)} pilot inputs; reports: {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.first, args.second, args.output)
