# Mốc 2 — Kết quả upstream sau sửa điều kiện v2

**Cập nhật sau chuẩn bị:** Bước 4 đã chạy trên bộ dữ liệu v3 giữ nguyên. Kết quả/model được chọn và giới hạn ở [step4_results.md](step4_results.md). Những đoạn “chưa chạy Bước 4” bên dưới mô tả thời điểm bàn giao dữ liệu, không phải trạng thái hiện tại.

**Trạng thái hiện hành 14/11/2026:** đã hoàn tất điều kiện kỹ thuật trước Bước 4 với lô **60 CV mới / 12 họ**, split **30/15/15** và **3.000 cặp có nhãn tự động** trên catalog 50 JD cố định. Lô 60 CV v2 cũ giữ development vì lỗi lineage. Hai run mới có 302 file giống byte; 64 test đạt. Xem [bàn giao hiện hành và lệnh PowerShell](pretraining_handoff.md). Các mục 1–7 bên dưới lưu quá trình upstream, CV v1 và kiểm toán v2; các số lượng split/nhãn lịch sử không thay thế kết quả hiện hành. **Chưa chạy Bước 4.**

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

## 4. 60 CV giả lập mới và chuẩn hóa metadata có bằng chứng

Đã tạo bộ **60 CV giả lập mới** (`generator_version=synthetic-career-scenarios-v1`, `cohort_id=jobapply-synthetic-60-v1`) từ [design.json](../../ml_data_assets/synthetic_cv_v1/design.json) và [scenarios.json](../../ml_data_assets/synthetic_cv_v1/scenarios.json) qua `python -m ml_data synthetic-cvs`:

- **Phân bố nhóm nghề:** 12 CV cho mỗi nhóm `Backend Python`, `Backend Java`, `Frontend`, `DevOps/Cloud` và `QA/Testing` (tổng 60 CV). Chưa tạo CV `Data Analyst` ở đợt này vì nhóm `Data Analyst` hiện có `0` JD ngoài pilot qua cổng chất lượng kỹ thuật; không tạo quota giả để tuyên bố đủ benchmark 6 nghề.
- **Độc lập kịch bản và giới hạn lineage:** viết chủ yếu bằng tiếng Việt kèm thuật ngữ công nghệ, đa dạng nhiệm vụ, stack, thời lượng và cách trình bày từ 60 kịch bản nghề nghiệp độc lập (`source_group = scenario:<cv_id>`), không sao chép JD đích, không xem ranking và không nhắm đạt nhãn `2` với một JD cụ thể; không viết lại 6 CV pilot (`0` nhóm nối với pilot) và không chứa PII thật. Tuy có 60 `source_group` kịch bản, toàn bộ 60 CV thuộc **6 họ khung sinh (`template_group`)** (`10` CV/họ = `2` CV/nghề × `5` nghề) và cùng một đợt tác giả kịch bản nên gom nhóm chuẩn tạo **6 nhóm CV độc lập** (`54` cạnh `template_group`, `0` cạnh gần trùng chéo họ). Đây là dữ liệu synthetic phục vụ phát triển/kiểm thử quy trình, không phải 60 ứng viên thật độc lập.
- **6 họ khung (`template_group`) và loại thời lượng (`experience_kind`):**
  - `employment_history` (`10` CV, `employment`): làm việc toàn thời gian (`14–54` tháng).
  - `incident_case` (`10` CV, `employment`): hồ sơ xử lý sự cố/vận hành thực tế (`16–48` tháng).
  - `personal_portfolio` (`10` CV, `project`): đồ án/dự án cá nhân (`5–11` tháng).
  - `internship_log` (`10` CV, `internship`): nhật ký thực tập (`3–6` tháng).
  - `contract_handover` (`10` CV, `contract`): hợp đồng ngắn hạn/bàn giao (`6–15` tháng).
  - `incomplete_account` (`10` CV, `unknown`): mô tả công việc/stack nhưng thiếu mốc thời gian rõ ràng, giữ `experience_json = "{}"` (không thay bằng `0` tháng và không suy từ tổng năm làm việc hay danh sách kỹ năng).
- **Schema và bằng chứng nguyên văn (`evidence.json`):**

| Cột | Ý nghĩa |
|---|---|
| `cv_id`, `cv_text` | ID ổn định (`CVX_<ROLE>_01..12`) và văn bản chuyên môn đã ẩn danh (`>= 80` ký tự chuẩn hóa) |
| `source_group` | Mã kịch bản gốc (`scenario:<cv_id>`); mọi biến thể cùng kịch bản giữ chung mã |
| `template_group` | Họ khung sinh (`synthetic-career-scenarios-v1:<family>`); không tách họ qua các partition |
| `is_synthetic` | `true` tường minh cho toàn bộ 60 CV |
| `role`, `skills`, `stack` | Metadata có câu bằng chứng nguyên văn và offset ký tự trong `evidence.json` |
| `experience_json` | JSON `scope -> months` có câu bằng chứng nguyên văn; `10` CV thiếu thời lượng giữ `{}` |
| `exposure`, `text_scope` | `prospective` (chưa dùng chỉnh parser/feature), `professional` |
| `lineage_json` | Lưu `generator_version`, `cohort_id`, `scenario_id`, `template_family`, `variant_index`, `variant_history` và `derived_from_cv_ids=[]` |

Xem [config mẫu CV](data_configs/new_cvs.template.json) và [config import kết hợp CV + JD v2](data_configs/synthetic_cv_jd_v2_import.json).

## 5. Import kết hợp và preview split `known-jd`

Lệnh `python -m ml_data expand-preview` kết hợp 60 CV giả lập với kho JD chuẩn của run `20261113_upstream_v2_01` (`dataset_version = synthetic-careers-v1-jd-v2-a3127c9fa6fa`, `3.122` bản ghi = `60` CV + `3.062` JD, `2.518` nhóm = `6` nhóm CV + `2.512` nhóm JD). Kiểm tra bất biến xác nhận toàn bộ `3.062` JD giữ nguyên 100% văn bản, quality flags, lineage, group/exposure và raw row (`888` keep = `100` development + `788` prospective; `65` bản trùng loại; `2.109` quarantine; closure development giữ nguyên `154` record). Chi tiết đầy đủ tại [receipt preview](reports/20261113-cv-jd-preview.json).

Preview split theo protocol **`known-jd`** (`seed=20261113`, Top `k=5`, tỷ lệ đích `60/20/20` áp lên nguyên nhóm CV, kho JD hợp lệ dùng chung là **788 JD** `keep` ngoài `development`):

| Partition preview | CV | Nhóm CV (`template_group`) | JD dùng chung | Cặp dự kiến |
|---|---:|---:|---:|---:|
| `train` | 30 | 3 (`employment_history`, `incident_case`, `incomplete_account`) | 788 | 90 |
| `validation` | 20 | 2 (`internship_log`, `personal_portfolio`) | 788 | 15.760 |
| `test` | 10 | 1 (`contract_handover`) | 788 | 7.880 |

- **Phân bố theo partition:**
  - **`train` (30 CV, 3 nhóm):** mỗi nghề 6 CV (`Backend Python: 6`, `Backend Java: 6`, `Frontend: 6`, `DevOps/Cloud: 6`, `QA/Testing: 6`); loại kinh nghiệm `{'employment': 20, 'unknown': 10}`; thiếu các loại `['contract', 'internship', 'project']`.
  - **`validation` (20 CV, 2 nhóm):** mỗi nghề 4 CV (`4 × 5 = 20`); loại kinh nghiệm `{'internship': 10, 'project': 10}`; thiếu các loại `['contract', 'employment', 'unknown']`.
  - **`test` (10 CV, 1 nhóm):** mỗi nghề 2 CV (`2 × 5 = 10`); loại kinh nghiệm `{'contract': 10}`; thiếu các loại `['employment', 'internship', 'project', 'unknown']`.
- **Nhận xét độ lệch và chống rò rỉ:** kiểm tra chống rò rỉ nhóm đạt (`leakage_check_passed=true`, `pilot_connected_groups=0`). Tuy nhiên vì chỉ có **6 họ khung (`template_group`)** và mỗi họ gắn với một kiểu lịch sử kinh nghiệm, việc giữ nguyên họ trong cùng partition làm các loại kinh nghiệm bị tách hẳn giữa `train`/`validation`/`test` và `test` chỉ có 1 họ (`contract_handover`). Chúng tôi giữ nguyên kết quả và báo rõ hạn chế này thay vì tách họ, sửa provenance hay đổi seed để ép tỷ lệ. Protocol `known-jd` chỉ đo khả năng xếp hạng cho CV mới trên kho JD đã biết, không đo tổng quát hóa sang JD mới.
- **Khối lượng cặp dự kiến (chưa tạo file cặp hay nhãn):**
  - **`train` (`mixed`):** kế hoạch lấy `3` cặp ngẫu nhiên + tối đa `2` cặp cho mỗi loại hard candidate (`same_role_diff_requirement`, `same_stack_diff_task`, `experience_gap`) trên mỗi CV (trần `270` cặp). Thực tế lấy được **90 cặp** (`uniform_random_without_replacement: 90`) và **thiếu 180 slot hard candidate** (`90` lượt thiếu nhóm CV × loại hard) vì cả `788` JD dùng chung hiện giữ `skills=[]`, `stack=[]`, `experience={}` chưa kiểm chứng (`missing_metadata = {'skills': 788, 'stack': 788, 'experience': 788}`). Không mặc định cặp khó là nhãn `0`.
  - **`validation` (`census`):** `20 CV × 788 JD` = **15.760 cặp**.
  - **`test` (`census`):** `10 CV × 788 JD` = **7.880 cặp**.
  - **Tổng cộng 3 partition:** **23.730 cặp** (`pair_files_created=0`, `labels_created=0`, `final_test_ready=false`).
- **`Data Analyst` vẫn thuộc phạm vi nghiên cứu:** có `9` JD gắn tag nguồn, `8` JD có dấu hiệu chức danh, `4` JD nối với pilot và **`0` JD ngoài pilot qua gate**. Bốn JD đã chọn để rà parser (`job_3d91bd66351c91e206c7`, `job_ce9d4b53148ccab5609b`, `job_f276ea42265aab730cdf`, `job_60e8ded349354f397062`) vẫn giữ `development`/`quarantine`. Cần khôi phục/bổ sung JD `Data Analyst` hợp lệ trước khi thêm CV và mở rộng benchmark sang nghề thứ sáu.

## 6. Kiểm toán benchmark ngày 14/11/2026

**Thay thế kết luận “Bước 1–3 hoàn tất” trước đây.** Run `20261113_benchmark_v2/run_08` có 308/1.000/500 cặp và 30 cặp đối chứng đúng như báo cáo, nhưng hash và schema hợp lệ không chứng minh split/nhãn đúng. Có 49 CV đổi họ template giữa v1/v2, 41 giữ nguyên nội dung. Kiểm tra đầy đủ ancestry nối cả 60 CV thành một nhóm; không có validation/test tách biệt. [Báo cáo từ dữ liệu thực](benchmark_audit.md), [receipt](reports/20261114-benchmark-audit.json).

`synthetic.py` hiện bắt buộc assets tổ tiên cho biến thể, snapshot tổ tiên và ghi `lineage.template_ancestors`. `grouping.py` nối mọi template lịch sử thay vì chỉ tên template mới. Không tự thay source group, đổi seed hoặc xóa lịch sử để ép 30/20/10.

[Config import kiểm toán](data_configs/benchmark_audit_import.json) trỏ tới run có đầy đủ ancestry; config benchmark v2 thiếu ancestry đã được xóa khi dọn công cụ cũ. `audit`/`sample` từ chối biến thể thiếu ancestry hoặc dataset thiếu các partition độc lập.

Metadata JD phiên bản mới giữ scope rõ ràng: tổng kinh nghiệm phần mềm không tự thành thời gian Python/React; thời lượng nhiều mệnh đề chưa rõ scope giữ unknown; mức tối đa/ưu tiên không thành tối thiểu. Thuật toán không khẳng định hiểu đầy đủ mọi yêu cầu. Con số 100% cũ chỉ đo phát hiện có ngưỡng trên tập development, không phải độ đúng toàn bộ scope/giá trị.

Đã bỏ công cụ calibration và yêu cầu người review. Giữ validator kỹ thuật và nguồn gốc nhãn `automatic_rule_proxy`, không biến thành gold. Nhãn thiếu căn cứ giữ trống; `complete=false` khi còn `insufficient_evidence`. `label-pairs` bắt buộc `--output` mới, giữ bản cặp nguồn. [Quy tắc hiện hành](annotation_guidelines.md).

**Kết luận kiểm toán lô v2 cũ:** cần các họ CV mới để có partition; lô cũ phải giữ development nguyên nhóm. Điều kiện này đã được xử lý bằng lô v3 ở mục 8; Bước 4 vẫn chưa chạy theo yêu cầu dừng. Khi thí nghiệm sau này, chỉ fit scaler/LR trên train, chọn trên validation rồi đánh giá test. So sánh cả baseline luật sinh nhãn và ablation text-only/metadata vì dùng cùng skill/stack/experience cho feature lẫn nhãn tạo sự phụ thuộc vòng tròn. Không bỏ cặp chưa có nhãn khi tính metric toàn catalog mà không báo độ phủ.

Data Analyst vẫn là mục tiêu nghiên cứu; cần JD mới/khôi phục section có bằng chứng ngoài development. Bộ 50 JD hiện là subset cố định, không chứng minh khả năng trên cả catalog 788 JD hoặc người dùng thật.

## 7. PowerShell kiểm toán và kiểm tra readiness

Đã gỡ lệnh dựng benchmark v2 và assets của nó. Snapshot kiểm toán vẫn được giữ để đối chiếu; kiểm tra lô hiện hành bằng `check-pretraining` ở mục 8. Các run chứa dữ liệu đầy đủ tiếp tục Git ignore. [Biên bản dọn dẹp](retired_cv_cleanup.md).

```powershell
Set-Location D:\JobApply
$auditRun = '.\ml_data_runs\20261114_benchmark_audit_02'
python -m ml_data verify --artifact $auditRun
if ($LASTEXITCODE -ne 0) { throw 'Artifact verification failed' }
python -m ml_data audit --dataset "$auditRun\dataset" --split "$auditRun\preview_split"
# partition_ready=false: kiểm toán lô cũ không tự biến thành split hợp lệ.
```

Tạo/export CV v1 riêng để tái tạo preview lịch sử (không phải xử lý lỗi lineage v2):

```powershell
$cvOut = '.\ml_data_runs\cv_render_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
python -m ml_data synthetic-cvs --assets .\ml_data_assets\synthetic_cv_v1 --output $cvOut
```

Kiểm thử:

```powershell
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
& .\.venv\Scripts\python.exe -m ruff check ml_data scripts/report-pretraining.py tests/ml/test_benchmark_prep.py tests/ml/test_automatic_labels.py tests/ml/test_pretraining.py
```

## 8. Điều kiện trước Bước 4 đã hoàn tất — lô v3

`prepare-experiment` kiểm checksum bốn run lịch sử, giữ catalog 50 ID, xuất 60 CV từ `ml_data_assets/independent_cv_v3/`, nhập cùng JD và ghi exposure development cho lô cũ trong bản dẫn xuất. V1 được thêm làm tham chiếu lịch sử chống trùng/lineage, không thêm vào train. Tất cả dữ liệu gốc và nhóm development được giữ nguyên.

Schema CV vẫn gồm `cv_id`, `cv_text`, `source_group`, `template_group`, `is_synthetic`, `role`, `skills`, `stack`, `experience_json`, `exposure`, `text_scope`; exporter ghi thêm lineage và bằng chứng nguyên văn/offset trong artifact. Kịch bản mới không có parent từ lô cũ. 12 họ là 12 khung viết thực tế, mỗi họ năm hồ sơ; vẫn cùng một tác giả AI/cohort, không phải nguồn ứng viên thật độc lập. 12 CV thiếu thời lượng giữ `{}`.

Known-jd: 30/15/15 CV thuộc 6/3/3 nhóm, mỗi tập đủ năm nghề và employment/project/internship/contract/unknown. Cả ba tập chỉ dùng catalog 50 JD; 788 JD đủ gate trong kho không đồng nghĩa 788 JD được dùng trong benchmark. Train census 1.500 cặp, validation/test mỗi tập 750; thêm 270 random/hard candidates làm chẩn đoán lấy mẫu, có thể tra nhãn theo pair ID trong train census. Không lấy mẫu lại để đạt lớp mong muốn.

Nhãn dùng `automatic-proxy-labeler-v3-scoped-coverage`; extraction giữ clause AND/OR/ưu tiên và scope thời lượng. Nhãn 1 biểu thị tương thích một phần theo nghề, kể cả hai bộ công nghệ đã biết khác nhau; không nhầm trường hợp đó với thiếu metadata. 3.000 nhãn số đầy đủ là điều kiện kỹ thuật, không phải độ đúng 100%. Catalog vẫn có bảy JD thiếu ngưỡng kinh nghiệm dùng được. Chi tiết, phân bố nhãn, giới hạn Recall@5 và Data Analyst ở [bàn giao](pretraining_handoff.md); [config import](data_configs/pretraining_v3_import.json), [receipt từ hai run thực](reports/20261114-pretraining-ready.json).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data check-pretraining --artifact .\ml_data_runs\20261114_pretraining_v3_01
if ($LASTEXITCODE -ne 0) { throw 'Pretraining checks failed' }
```

22 gate đạt, hai run có 302/302 file giống byte. **Dừng trước Bước 4**: chưa tính BM25/E5, fit model, chọn model theo validation hay tính metric test mới. Không có vòng người review/calibration; chưa có bằng chứng chất lượng trên người dùng thật.
