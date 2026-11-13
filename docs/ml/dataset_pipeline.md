# Mốc 2 — Kiểm chứng upstream, nhập JD và chuẩn bị lô mở rộng

Ngày 13/11/2026: đã kiểm chứng thực tế ba file CSV upstream tại thư mục gốc (`job_descriptions.csv`, `jobs_clean.csv`, `jobs_matching.csv`), đối chiếu liên kết bốn giai đoạn `raw → clean → matching → pilot`, nhập kho JD chuẩn vào pipeline `python -m ml_data` và chọn lô mở rộng đầu tiên gồm **64 JD development** ([danh sách chi tiết](reports/20261113-upstream-jd-selection.json), [biên bản tổng hợp](reports/20261113-data-preparation.json)). Ba file CSV nguồn và toàn bộ 33 file dữ liệu pilot gốc được giữ nguyên byte. **Chưa khóa split chính thức và chưa tạo cặp gán nhãn mới khi chưa bổ sung các nhóm CV mới.** Mọi báo cáo ranking giữ chuẩn Top 5 (`k=5`); chưa train lại model hoặc nhập JD lịch sử vào database ứng dụng.

## 1. Kiểm kê ba file CSV upstream thực tế

Ba file được đọc bằng `csv.reader` chuẩn của Python (xử lý đúng dòng văn bản nhiều hàng trong ngoặc kép) và giữ nguyên byte gốc:

| File | Kích thước (bytes) | SHA256 | Encoding thực tế | Số record | Số cột | Khóa định danh |
|---|---:|---|---|---:|---:|---|
| `job_descriptions.csv` | `11.090.108` | `52801f88a4f4273a519936823cd74c98d8313e59034b60c42108465df87fd852` | Không phải UTF-8 hợp lệ (lỗi byte `0xfd` tại vị trí `1727`; đọc bảo toàn bằng `utf-8/surrogateescape`) | `3.101` | `11` | Không có `job_id`; định danh theo số thứ tự record `1..3101` và `(site, job_url)` |
| `jobs_clean.csv` | `14.384.924` | `a9308c6eb4a59b7acf6b8a0996158b0e396e4e27040d9bc0ac5d81e1234638d3` | `UTF-8 BOM` hợp lệ | `3.062` | `25` | `job_id` duy nhất (`duplicate_id_excess=0`) |
| `jobs_matching.csv` | `11.197.747` | `2f77164049d1e29788c3b68bdc017836ffdbc3d96b8def723c1f5dc4d32fb4ab` | `UTF-8 BOM` hợp lệ | `3.062` | `23` | `job_id` duy nhất (`duplicate_id_excess=0`), `pipeline_version=1.0.0` |

Chi tiết kiểm tra chất lượng trên từng file:

- **`job_descriptions.csv` (3.101 record):**
  - Cột: `title, company, company_image_url, location, description, site, job_url, it_role_type, main_programming_languages, key_technologies, city`.
  - Nguồn theo `site`: TopCV `1.133`, LinkedIn `1.039`, ITViec `929` (khớp báo cáo lịch sử).
  - Lỗi mã hóa chữ: `2.669` dòng chứa byte không hợp lệ UTF-8; `3.075` dòng chứa ký tự thay thế `U+FFFD` (`703.267` lần xuất hiện).
  - Giá trị thiếu/rỗng: không có ô chuỗi rỗng, nhưng có JSON list rỗng `[]` ở `main_programming_languages` (`334` dòng) và `key_technologies` (`223` dòng). Có `1` dòng `description` dưới 40 ký tự (dòng `1141`, dài 12 ký tự).
  - Trùng và gần trùng trên `description` (chỉ mang tính chẩn đoán do hỏng encoding): `31` bản ghi dư trùng nguyên văn, `40` bản dư sau chuẩn hóa NFKC/casefold, `427` cặp gần trùng (Jaccard 3-gram $\ge 0{,}85$).
- **`jobs_clean.csv` (3.062 record):**
  - Đã khử hoàn toàn lỗi byte UTF-8 và ký tự `U+FFFD` (`0` dòng lỗi). Nguồn theo `site`: TopCV `1.098`, LinkedIn `1.035`, ITViec `929`.
  - Giá trị thiếu: `city` (`134`), `it_role_type` (`31`), `role_normalized_candidate` (`31`); JSON list rỗng ở `experience_mentions_json` (`1.608`), `review_flags_json` (`1.073`), `programming_languages_candidate_json` (`455`), `languages_source_normalized_json` (`374`), `technologies_source_normalized_json` (`220`), `skills_candidate_json` (`27`).
  - Lỗi công thức bảng tính (`#NAME?`...): `1` dòng ở `description`.
  - Trùng và gần trùng trên `description`: `27` bản dư trùng nguyên văn, `37` bản dư sau chuẩn hóa, `610` cặp gần trùng.
- **`jobs_matching.csv` (3.062 record):**
  - Không còn lỗi UTF-8 hay `U+FFFD`. Mọi dòng đều có `match_text` khác rỗng (`16` dòng dưới 40 ký tự).
  - Giá trị thiếu ở các cột thành phần: `unclassified_professional_text` (`2.492`), `preferred_requirements_text` (`2.421`), `tasks_text` (`816`), `requirements_text` (`470`), `city` (`134`), `title_for_matching` (`2`).
  - Lỗi công thức bảng tính (`#NAME?` do dòng bắt đầu bằng dấu `-`/`=` trong bảng tính trước khi xuất CSV): `tasks_text` (`713` dòng), `preferred_requirements_text` (`193` dòng), `unclassified_professional_text` (`181` dòng), `requirements_text` (`134` dòng); `match_text` có `0` ô `#NAME?` vì được ghép từ các dòng đã chọn trong mô tả.
  - Trạng thái trích xuất upstream (`extraction_status`): `ok` (`2.462`), `sections_plus_fallback` (`371`), `fallback_only` (`196`), `insufficient_text` (`33`). Cờ `needs_review=True` trên `1.431` dòng.
  - Trùng và gần trùng trên `match_text`: `203` bản dư trùng nguyên văn, `205` bản dư sau chuẩn hóa, `408` cặp gần trùng.
- **Provenance biết được và chưa biết:**
  - Biết được: checksum SHA256 của cả ba file, `pipeline_version="1.0.0"` trong `jobs_matching.csv`, phân bố `site`, URL từng tin (`job_url`) và liên kết `source_row_number` / `source_records_json` / `source_description_sha256` / `source_match_text_sha256`.
  - Chưa biết: thời điểm cạo dữ liệu (crawl timestamp), commit chính xác của kho nguồn `SonPhatTranDeveloper/IT-Job-Posting`, điều kiện cấp phép gốc và script/notebook đã sinh ra `jobs_clean.csv` cùng `jobs_matching.csv`.

## 2. Đối chiếu liên kết `raw → clean → matching → pilot`

Không nối ba CSV thành ba nguồn độc lập; chúng là các giai đoạn kế tiếp nhau của cùng một kho JD:

1. **`job_descriptions.csv` (3.101) → `jobs_clean.csv` (3.062):**
   - Mỗi dòng trong `jobs_clean.csv` liên kết về dòng chính trong `job_descriptions.csv` qua `source_row_number` (`3.062` dòng chính duy nhất) và danh sách đầy đủ trong `source_records_json` (thêm `38` dòng phụ được gộp trùng, khớp tổng `duplicate_count` tăng thêm `38`).
   - Toàn bộ `3.100 / 3.101` tham chiếu (`3.062` chính + `38` phụ) khớp chính xác `(site, job_url)` với `job_descriptions.csv` (`invalid_reference_links=0`).
   - Chỉ có đúng **1 dòng raw không xuất hiện** trong `jobs_clean.csv`: dòng `1141` (`description` dài 12 ký tự). Đây là quan sát thực nghiệm từ dữ liệu; lý do loại bỏ lịch sử không tự suy diễn vượt quá bằng chứng độ dài mô tả.
   - Thay đổi nội dung giữa dòng chính raw và clean (chủ yếu do sửa lỗi mã hóa tiếng Việt và chuẩn hóa địa점/công ty): `city` (`3.058`), `description` (`2.849`), `location` (`1.998`), `company` (`1.210`), `title` (`693`), `it_role_type` (`42`), `company_image_url` (`13`), `key_technologies` (`2`).
2. **`jobs_clean.csv` (3.062) → `jobs_matching.csv` (3.062):**
   - Tập `job_id` trùng khớp tuyệt đối `3.062 / 3.062` (`added_ids=[]`, `removed_ids=[]`).
   - Hash `source_description_sha256` trong `jobs_matching.csv` khớp `sha256(clean.description)` trên **`3.061 / 3.062` dòng**; chỉ có `1` bản ghi lệch hash mô tả gốc là `job_906e26bf2136f879aba5` (được gắn cờ quarantine khi import).
   - Các trường metadata chung (`title`, `company`, `location`, `city`) tiếp tục được chuẩn hóa trên `2.741` dòng.
3. **`jobs_matching.csv` (3.062) → `jobapply_pilot_v1/jobs_pilot.csv` (50):**
   - Toàn bộ **`50 / 50` JD pilot** đều tìm thấy trong `jobs_matching.csv` theo `job_id`.
   - Toàn bộ **`50 / 50` JD pilot** khớp chính xác `source_match_text_sha256` với `sha256(jobs_matching.match_text)` trước khi chỉnh sửa.
   - Có `11` JD pilot thay đổi `match_text` so với `jobs_matching.csv`, khớp nhật ký `jobapply_pilot_v1/pilot_edits.csv`.
4. **Script lịch sử trong workspace:**
   - Trong repo chỉ có `jobapply_pilot_v1/prepare_pilot.py` (đọc `jobs_clean.csv` và `jobs_matching.csv` để trích 50 JD pilot). Không có script/notebook lịch sử tạo ra `jobs_clean.csv` và `jobs_matching.csv` (`historical_pipeline_reproduced=false`).
   - Do đó, `ml_data/upstream.py` (`adapter_version="upstream-observation-v1"`) được xây dựng làm pipeline chuẩn hóa và kiểm định phiên bản mới từ dữ liệu thực tế, ghi nhận rõ mọi khác biệt quan sát được.

## 3. Import JD bằng `ml_data/` và phân loại chất lượng

`python -m ml_data upstream` chọn `jobs_matching.csv` làm giai đoạn chuẩn (`canonical_jd.csv`, namespace `it-job-posting-matching`), đồng thời lưu snapshot nguyên byte cả ba CSV vào `snapshots/` và liên kết từng `job_id` về `source_row_number`, `source_records_json`, `job_url`, `content_group_id` và `clean_description_sha256` trong `lineage.jsonl`. Cấu hình import đã xác minh được lưu tại [docs/ml/data_configs/upstream_jd_import.json](data_configs/upstream_jd_import.json).

### Quy tắc rà chất lượng và phân loại (`3.062` JD → `2.512` nhóm)

- **Metadata thiếu giữ `unknown`:** không tự suy số tháng kinh nghiệm theo kỹ năng, không lấy các trường công nghệ do LLM gợi ý ở upstream làm nhãn chuẩn (`missing.skills=3062`, `missing.stack=3062`, `missing.experience=3062`).
- **Trích xuất có bằng chứng (`rule_version="upstream-observation-v1"`):** các dấu hiệu nhóm nghề (`role_evidence`), câu nhắc số năm/tháng kinh nghiệm (`experience_mentions`), từ khóa bắt buộc (`must_mentions`) và từ khóa dễ nhầm giữa các nghề (`shared_keyword_mentions`) đều lưu kèm tên cột, vị trí ký tự `start..end` và đoạn trích nguyên văn trong `selection_features.json`.
- **Kết quả phân loại 3.062 JD:**
  - **`keep` (dùng được ngay): `888` JD** (`100` JD thuộc vùng `development_only`, `788` JD `prospective` sẵn sàng cho chia tập khi có CV mới). Đạt toàn bộ điều kiện: `extraction_status="ok"`, `needs_review=False`, có đủ cả `tasks_text` và `requirements_text` ($\ge 20$ ký tự), không có lỗi `#NAME?`, không hỏng mã hóa, `match_text` $\ge 40$ ký tự và khớp hash liên kết `clean → matching`.
  - **`exclude_exact_duplicate` (loại bản trùng chính xác): `65` JD** (`8` trong `development_only`, `57` ngoài development). Các bản ghi này trùng hoàn toàn `match_text` chuẩn hóa với một bản `keep` đã giữ lại trong cùng nhóm; dữ liệu gốc vẫn được bảo toàn trong `records.jsonl`.
  - **`quarantine` (cách ly chờ xử lý/sửa parser): `2.109` JD** (`46` trong `development_only`, `2.063` ngoài development). Một JD có thể có nhiều lý do cách ly đồng thời:
    - Thiếu hoặc quá ngắn mục nhiệm vụ `missing_or_short_section:tasks_text`: `1.530` JD
    - Cờ `upstream_needs_review` (`needs_review=True`): `1.431` JD
    - Lỗi công thức bảng tính `#NAME?` ở `tasks_text`: `713` JD; ở `preferred_requirements_text`: `193` JD; ở `unclassified_professional_text`: `181` JD; ở `requirements_text`: `134` JD
    - Thiếu hoặc quá ngắn mục yêu cầu `missing_or_short_section:requirements_text`: `605` JD
    - Trích xuất phụ thuộc fallback: `upstream_extraction:sections_plus_fallback` (`371` JD), `upstream_extraction:fallback_only` (`196` JD), `upstream_extraction:insufficient_text` (`33` JD)
    - `match_text` dưới 40 ký tự (`empty_or_short_text_under_40_chars`): `16` JD
    - Lệch hash mô tả giữa clean và matching (`clean_description_hash_unverified`): `1` JD (`job_906e26bf2136f879aba5`)
- **Bảo vệ pilot và gom nhóm bắc cầu:**
  - `50` JD pilot kéo theo `18` bản ghi upstream khác cùng `content_group_id`, cùng `job_url` hoặc trùng/gần trùng văn bản (Jaccard 3-gram $\ge 0{,}85$), tạo thành **`68` bản ghi liên quan pilot** được khóa cứng ở `development`.

## 4. Lô JD mở rộng đầu tiên (`64` JD development)

Mục tiêu chọn `12` JD mỗi nhóm nghề trên 6 nhóm (`72` JD, nằm trong khoảng `60–90` JD), ngoài toàn bộ nhóm liên quan pilot, mỗi nhóm nội dung (`group_id`) chỉ lấy tối đa 1 JD, ưu tiên JD đạt cổng chất lượng (`keep`), có mô tả tiếng Việt ($\ge 20$ ký tự có dấu tiếng Việt) và đa dạng mức kinh nghiệm, yêu cầu bắt buộc/ưu tiên cùng từ khóa giao thoa (`Python`, `Java`, `Docker`, `AWS`, `SQL`, `React`...).

| Nhóm nghề | Mục tiêu | JD ứng viên ngoài pilot | Nhóm ngoài pilot | Nhóm đạt `keep` | Đã chọn | Quyết định cổng | Thiếu hụt (`shortages`) |
|---|---:|---:|---:|---:|---:|---|---:|
| `Backend Python` | 12 | 101 | 90 | 28 | **12** | 12 `keep` | 0 |
| `Backend Java` | 12 | 348 | 290 | 121 | **12** | 12 `keep` | 0 |
| `Frontend` | 12 | 224 | 190 | 55 | **12** | 12 `keep` | 0 |
| `DevOps` | 12 | 48 | 48 | 14 | **12** | 12 `keep` | 0 |
| `QA/Testing` | 12 | 150 | 141 | 43 | **12** | 12 `keep` | 0 |
| `Data Analyst` | 12 | 4 | 4 | 0 | **4** | 4 `quarantine` (dùng sửa parser) | **8** |
| **Tổng cộng** | **72** | **875** | **763** | **261** | **64** | **60 `keep`, 4 `quarantine`** | **8** |

- **Báo thiếu trung thực ở nhóm `Data Analyst`:** ngoài 4 JD đã nằm trong pilot, toàn bộ kho upstream 3.062 JD chỉ còn đúng **4 nhóm `Data Analyst`** (`job_1841450223593372053b`, `job_3bc510346aa6e204ff23`, `job_772ca897a63e0bb9268a`, `job_d10d9deca08f131f445c`), và cả 4 đều ở trạng thái `quarantine` do thiếu tách mục `tasks_text` riêng. Pipeline chọn 4 JD này làm mẫu phát triển parser và ghi nhận thiếu `8` JD (`shortages={"Data Analyst": 8}`), tuyệt đối không sửa nội dung hoặc bịa JD để lấp đủ 12.
- **Đặc trưng thực tế của 64 JD đã chọn:**
  - `44 / 64` JD có mô tả tiếng Việt rõ rệt; `55 / 64` JD có biểu thức số năm/tháng kinh nghiệm; `33 / 64` JD có từ khóa điều kiện bắt buộc; `10 / 64` JD có mục yêu cầu ưu tiên riêng (`preferred_requirements_text`).
  - Toàn bộ 64 JD (cùng 22 bản ghi cùng nhóm với chúng, tổng cộng `86` bản ghi ngoài nhóm pilot) được đánh dấu `exposure="development"` (`purpose="development/parser only"`, chưa phải final test). Khi cộng với `68` bản ghi liên quan pilot, vùng `development` có `154` bản ghi (`100` `keep`, `46` `quarantine`, `8` `exclude_exact_duplicate`) thuộc `114` nhóm.
  - Phần còn lại ngoài `development` có **`788` JD `keep` (`prospective`)** sẵn sàng cho các partition `train/validation/test` (với preview `new-both` seed `20261113`: `476` train, `155` validation, `157` test; với `known-jd`: `788` `shared`). Tuy nhiên `partition_ready=false` vì chưa có CV mới (`readiness_blockers=["no_CV_in_train", "no_CV_in_validation", "no_CV_in_test"]`).

## 5. Hợp đồng schema CV mới cần bổ sung để đi tiếp

Để khóa split chính thức và lấy mẫu cặp huấn luyện/đánh giá ở bước tiếp theo, cần bổ sung file CSV CV mới theo đúng hợp đồng nguồn trong [docs/ml/data_configs/new_sources.template.json](data_configs/new_sources.template.json):

| Trường chuẩn trong config | Cột CSV đề xuất | Yêu cầu bắt buộc khi chuẩn bị CV mới |
|---|---|---|
| `external_id` | `cv_id` | Mã CV duy nhất, ổn định (ví dụ `CV_EXP_001`). |
| `text` | `cv_text` | Văn bản chuyên môn đã ẩn danh PII, tối thiểu 40 ký tự. |
| `source_group` | `source_group` | Mã nguồn gốc hồ sơ trước mọi biến thể/dịch/rút gọn. Mọi biến thể từ cùng một hồ sơ gốc phải dùng chung `source_group` để không rò rỉ giữa train và test. |
| `template_group` | `template_group` | Bắt buộc nếu `is_synthetic=true`: mã họ template/generator. Không đặt mỗi CV một mã riêng nếu dùng chung khung sinh dữ liệu. |
| `role` | `role` | Nhóm nghề mục tiêu (`Backend Python`, `Backend Java`, `Frontend`, `DevOps`, `QA/Testing`, `Data Analyst`) phục vụ kiểm tra phân bố và lấy mẫu. |
| `skills`, `stack` | `skills`, `stack` | Danh sách phân tách bằng `;` (ví dụ `python;sql;docker`) hoặc để trống nếu chưa trích xuất; không gộp bằng dấu phẩy chưa chuẩn hóa. |
| `experience` | `experience_json` | JSON object ánh xạ `scope -> số tháng có bằng chứng` (ví dụ `{"backend python": 24}`). Nếu chưa rõ thời lượng theo scope thì để trống `{}`/rỗng; không suy từ tuổi hoặc năm tốt nghiệp. |
| `is_synthetic` | `is_synthetic` | `true` hoặc `false` tường minh; bỏ trống sẽ bị quarantine. |
| `exposure` | `exposure` | `prospective` cho các CV dùng để chia `train/validation/test`; `development` nếu CV đã dùng để chỉnh parser/feature. |
| `text_scope` | `text_scope` | `professional` sau khi đã kiểm tra loại bỏ thông tin cá nhân (mặc định `unreviewed` sẽ bị quarantine). |

## 6. Lệnh PowerShell kiểm chứng và tái tạo

Chạy từ thư mục gốc `D:\JobApply` (chỉ cần thư viện chuẩn Python, không cần mạng hay Docker):

```powershell
Set-Location D:\JobApply
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$base = ".\ml_data_runs\$runId"

# 1. Kiểm kê ba CSV upstream và các script trong workspace
.\.venv\Scripts\python.exe -m ml_data inventory --output "$base\inventory"
if ($LASTEXITCODE -ne 0) { throw 'Inventory failed' }

# 2. Kiểm chứng liên kết raw -> clean -> matching -> pilot, import JD và chọn lô mở rộng
.\.venv\Scripts\python.exe -m ml_data upstream --source-dir . --output "$base\upstream"
if ($LASTEXITCODE -ne 0) { throw 'Upstream import failed' }

# 3. Chạy lặp lần hai để kiểm chứng tái tạo giống hệt từng byte và xác minh manifest
.\.venv\Scripts\python.exe -m ml_data upstream --source-dir . --output "$base\upstream_repeat"
if ($LASTEXITCODE -ne 0) { throw 'Repeat upstream import failed' }
.\.venv\Scripts\python.exe -m ml_data verify --artifact "$base\upstream"
.\.venv\Scripts\python.exe -m ml_data verify --artifact "$base\upstream\dataset"

# 4. Kiểm tra preview split trên kho JD đã import (chưa khóa split vì chưa có CV mới)
.\.venv\Scripts\python.exe -m ml_data split --dataset "$base\upstream\dataset" --mode known-jd --seed 20261113 --output "$base\split_known_jd"
.\.venv\Scripts\python.exe -m ml_data split --dataset "$base\upstream\dataset" --mode new-both --seed 20261113 --output "$base\split_new_both"
```

Chạy bộ kiểm thử đơn vị (41 test trong môi trường ML, hoặc 23 test pipeline/upstream bằng Python chuẩn):

```powershell
.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/ml -v
```
