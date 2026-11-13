# Mốc 2 — Kết quả upstream sau sửa điều kiện v2

Ngày 13/11/2026. Báo cáo được sinh từ hai run đã kiểm checksum và so sánh **51 file giống byte**. Không lấy lại số liệu/ID từ bản báo cáo v1. [Receipt đầy đủ](reports/20261113-data-preparation.json), [danh sách JD](reports/20261113-upstream-jd-selection.json), [schema cột thực tế](schemas/upstream_columns.json).

## 1. Ba file thực tế và quan hệ

| File | Record | Cột | Dòng có byte UTF-8 lỗi | Dòng có U+FFFD |
|---|---:|---:|---:|---:|
| `job_descriptions.csv` | 3101 | 11 | 2669 | 3075 |
| `jobs_clean.csv` | 3062 | 25 | 0 | 0 |
| `jobs_matching.csv` | 3062 | 23 | 0 | 0 |

Raw chưa có `job_id`; dùng số thứ tự record CSV và URL/site để đối chiếu. Clean và matching là UTF-8 BOM hợp lệ, mỗi file có 3.062 ID duy nhất. Raw không phải UTF-8 hợp lệ; parser dùng `surrogateescape` chỉ để giữ cấu trúc CSV và byte lỗi, không phục hồi chữ đã mất. Không giải thích clean là kết quả sửa thành công từ chính bản raw hỏng hiện có.

- Raw → clean: 3100 tham chiếu khớp số dòng/URL/site; 3062 dòng chính và 38 dòng phụ được khai báo gộp. Dòng [1141] không được tham chiếu, mô tả dài 12 ký tự. Đó là quan sát; lý do/thao tác lịch sử chưa có script chứng minh.
- Clean → matching: cùng 3062 ID, không thêm/mất ID; 3061 hash mô tả khớp. ID lệch là `job_906e26bf2136f879aba5`, mô tả clean chứa `#NAME?`. Có 2741 dòng thay đổi ít nhất một trường chung; không mặc định nguyên nhân thay đổi.
- Matching → pilot: 50/50 ID và 50/50 hash trước chỉnh sửa khớp; 11 văn bản pilot khác matching. `prepare_pilot.py` và nhật ký pilot có trong repo; chưa tìm được script/notebook tạo hai giai đoạn clean/matching trong phạm vi workspace đã kiểm kê. Chưa tái tạo lịch sử.

Ba CSV là ba giai đoạn cùng kho, chỉ import **matching một lần**, giữ raw/clean làm context snapshots. Số lượng 3.101 → 3.062 → 3.062 khớp lịch sử, nhưng không đủ chứng minh nguyên vẹn nội dung.

| File | Bản dư trùng text nguyên văn | Bản dư trùng sau chuẩn hóa | Cặp gần trùng giữa text duy nhất |
|---|---:|---:|---:|
| `job_descriptions.csv` | 31 | 40 | 427 |
| `jobs_clean.csv` | 27 | 37 | 610 |
| `jobs_matching.csv` | 203 | 205 | 408 |

Near duplicate dùng Jaccard shingle 3 token ≥0,85, có thể nối bắc cầu; không phải chứng nhận tương đương ngữ nghĩa. Kết quả raw hỏng chỉ là chẩn đoán. Checksum, độ lớn, phân bố nguồn, thiếu dữ liệu và lỗi từng cột nằm trong receipt. Source revision/ngày thu thập/quyền phân phối chưa rõ; `pipeline_version=1.0.0` là chuỗi trong CSV, không phải script đã khôi phục.

## 2. Điều kiện đã sửa và kết quả import

Quy tắc **`upstream-observation-v2`**: chỉ qua gate khi `extraction_status=sections_found` **và** `needs_review=false` **và** `review_flags_json=[]`. Trạng thái boolean phải đọc được; `human_reviewed` không được biến thành xác nhận nhãn. Nguồn thực tế toàn bộ `human_reviewed=FALSE`. Tên trạng thái `ok` trong tài liệu cũ là sai.

Một hằng số chung **80 ký tự sau NFKC/chuẩn hóa khoảng trắng** áp cho text chính của importer và ba trường `tasks_text`, `requirements_text`, `match_text` ở gate upstream. Chức danh và mục ưu tiên không chịu ngưỡng tối thiểu này. Lỗi bảng tính, ký tự thay thế, hash/identity không kiểm chứng được vẫn bị cách ly dù cờ nguồn ghi FALSE. Ngưỡng là quy tắc kiểm tra kỹ thuật, không chứng minh đủ nội dung chuyên môn.

| Quyết định | JD | Ý nghĩa |
|---|---:|---|
| `keep` | 888 | Qua gate kỹ thuật; chưa có nhãn CV–JD hay xác nhận chuyên gia |
| `exclude_exact_duplicate` | 65 | Bản dư cùng text chuẩn hóa với một bản keep; vẫn giữ raw/provenance |
| `quarantine` | 2109 | Cần rà nguồn/parser, không đưa vào split hoặc huấn luyện |

Trong keep, **100 development** và **788 prospective**. Prospective chỉ là ứng viên cho bước sau, chưa phải train/test sẵn sàng. Tổng 2512 nhóm; 68 record nối với pilot đã bị giữ development trước khi chọn lô mới.

Lý do cách ly có thể chồng nhau, **không cộng các số dưới thành tổng JD**:

- `clean_description_hash_unverified`: 1.
- `empty_or_short_text_under_80_chars`: 26.
- `missing_or_short_section:match_text`: 26.
- `missing_or_short_section:requirements_text`: 605.
- `missing_or_short_section:tasks_text`: 1530.
- `spreadsheet_error:preferred_requirements_text`: 193.
- `spreadsheet_error:requirements_text`: 134.
- `spreadsheet_error:tasks_text`: 713.
- `spreadsheet_error:unclassified_professional_text`: 181.
- `upstream_extraction:fallback_only`: 196.
- `upstream_extraction:insufficient_text`: 33.
- `upstream_extraction:sections_plus_fallback`: 371.
- `upstream_needs_review`: 1431.
- `upstream_review_flags_present`: 1431.

Các ô `#NAME?` là lỗi quan sát được; chưa xác minh phần mềm hoặc thao tác nào gây ra. Không tự tái tạo đoạn bị mất. `match_text` gốc không bị sửa. Skills/stack/scoped experience chưa kiểm chứng giữ rỗng/unknown, không biến thành 0 tháng. Dấu hiệu nghề, số năm/tháng, từ bắt buộc và từ khóa chỉ phục vụ lấy mẫu, lưu rule version cùng trường/offset/trích đoạn; không phải bộ trích xuất kinh nghiệm đúng scope.

## 3. Lô development và Data Analyst

Đã chọn **64 JD** ngoài các nhóm pilot: **60 keep và 4 quarantine để rà parser**. Mục tiêu 12/nhóm; một JD mỗi group. Quarantine trong lô không phải JD huấn luyện. Lô có 44 JD có dấu hiệu tiếng Việt, 55 có nhắc thời lượng, 33 có từ chỉ điều kiện bắt buộc và 10 có mục ưu tiên; đều là dấu hiệu văn bản, chưa xác minh nghĩa.

| Nhóm lấy mẫu | Record ứng viên ngoài pilot | Group ứng viên | Record qua gate | Đã chọn |
|---|---:|---:|---:|---:|
| Backend Java | 348 | 290 | 121 | 12 |
| Backend Python | 101 | 90 | 28 | 12 |
| Data Analyst | 4 | 4 | 0 | 4 |
| DevOps | 48 | 48 | 14 | 12 |
| Frontend | 224 | 190 | 55 | 12 |
| QA/Testing | 150 | 141 | 43 | 12 |

Không cộng cột ứng viên giữa nghề như các mẫu độc lập vì một JD có thể có nhiều dấu hiệu. Seed `20261113`; ưu tiên keep, dấu hiệu tiếng Việt, đa dạng biểu thức kinh nghiệm/ưu tiên và tie-break xác định. Mọi ID, lý do, evidence và quyết định được lưu trong danh sách JSON.

**Data Analyst:** nguồn clean gắn tag cho 9 JD; quy tắc chức danh nhận 8 JD, gồm `Data Analytics Specialist`. Có 1 JD chỉ mang tag nguồn (`Analytics Engineer`), chưa tự coi là cùng nhiệm vụ để đủ quota. Có 4 JD thuộc pilot, còn **0 JD ngoài pilot qua gate** trong nhóm kiểm kê này. Chọn 4 trường hợp để sửa parser, thiếu 8 so với mục tiêu 12. Không kết luận toàn thị trường/kho chỉ có từng ấy Data Analyst; quy tắc tên nghề còn có giới hạn.

ID Data Analyst thực chọn: `job_3d91bd66351c91e206c7`, `job_ce9d4b53148ccab5609b`, `job_f276ea42265aab730cdf`, `job_60e8ded349354f397062`.

Lô mới và closure nhóm chứa 86 record development ngoài nhóm pilot. Chưa tạo CV mới, cặp nhãn hay khóa split trong hai run v2. Không dùng preview split cũ làm split chính thức. Chưa train lại, chưa chấm hai reviewer, không nhập JD lịch sử vào database app hoặc đổi API/UI/Docker/VM.

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
| `experience_json` | JSON scope → tháng có bằng chứng; thiếu giữ `{}`/trống, không suy từ tuổi/skill liệt kê |
| `exposure`, `text_scope` | development nếu đã dùng chỉnh phương pháp; prospective nếu ứng viên chia tập. `professional` sau khi đã rà text, mặc định unreviewed cách ly |

Tạo nguồn CV có version/manifest và quyền sử dụng; gom lineage trước, rà phân bố và chọn protocol `known-jd` hoặc `new-both` khi đã có CV đủ độc lập. Không mặc định ghép mọi CV với JD không được chọn là nhãn 0. [Config template](data_configs/new_cvs.template.json) chưa chứa CV thực tế.

## 5. PowerShell tái tạo và sinh báo cáo

Các output lớn, nguồn và text đầy đủ nằm trong `ml_data_runs/` đã Git ignore; chỉ schema/config/receipt được giữ trong repo. Ba nguồn local cần đi kèm khi tái tạo. [Config export hiện hành](data_configs/upstream_jd_import.json) trỏ tới canonical/context của run v2 local, không dùng được chỉ bằng clone mà thiếu run.

```powershell
Set-Location D:\JobApply
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$base = ".\ml_data_runs\$runId"
python -m ml_data upstream --source-dir . --output "$base\first" --seed 20261113
if ($LASTEXITCODE -ne 0) { throw 'First upstream run failed' }
python -m ml_data upstream --source-dir . --output "$base\second" --seed 20261113
if ($LASTEXITCODE -ne 0) { throw 'Second upstream run failed' }
python .\scripts\report-upstream.py --first "$base\first" --second "$base\second" --output "$base\reports"
if ($LASTEXITCODE -ne 0) { throw 'Reproducibility or original-file check failed' }
python -m ml_data verify --artifact "$base\first\dataset"
```

Script report chỉ tạo output mới, xác minh nguồn/pilot và mọi hash trước khi xuất báo cáo. Không có lệnh tạo split ở lượt này. Chạy test:

```powershell
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
& .\.venv\Scripts\python.exe -m ruff check ml_data scripts/report-upstream.py tests/ml/test_upstream.py
```
