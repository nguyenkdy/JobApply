# Mốc 2 — Nhập dữ liệu, chia nhóm và chuẩn bị cặp

Ngày 13/11/2026: đã triển khai công cụ offline `python -m ml_data`. **Chưa có dataset mở rộng hoặc final test sẵn sàng.** Theo quyết định hiện tại, chưa triển khai vòng calibration hai reviewer. Giữ nguyên pilot 50 JD × 6 CV, nhãn AI và provenance; không đổi sang `human_verified`. Mọi báo cáo ranking tiếp tục dùng Top 5; chưa train/chọn model mới.

## Dữ liệu thực có và phần thiếu

Trong phạm vi workspace đã quét, kể cả file dữ liệu bị Git ignore, chưa thấy `job_descriptions.csv`, `jobs_clean.csv`, `jobs_matching.csv`. Báo cáo inventory ghi rõ thư mục dependency/cache được bỏ qua và lỗi đọc nếu có. Không tìm trên máy khác, không tải nguồn mới và không khẳng định các file không tồn tại bên ngoài workspace.

`jobapply_pilot_v1/prepare_pilot.py` **tiêu thụ** hai file `--clean`/`--matching`, chọn 50 ID từ `selection_manifest.csv`, sửa nội dung có nhật ký và dựng 6 CV giả lập. Script này không tạo upstream clean/matching. Chưa tìm thấy script/notebook tái tạo hai bước trước đó. Các số 3.101 → 3.062 trong báo cáo cũ chưa được kiểm chứng từ CSV nguồn ở đợt này.

Dữ liệu sẵn có: `jobs_pilot.csv` 50 JD, `cvs_synthetic.csv` 6 CV synthetic, 300 nhãn `ai_draft`, chú thích kinh nghiệm pilot, manifest lựa chọn/chỉnh sửa và các baseline run. Phiếu calibration 24 cặp Mốc 1 vẫn trống, được giữ nguyên. Công cụ mới không nhập nhãn đó, không đọc database app và không biến JD lịch sử thành tin đang tuyển.

Cần bổ sung ba CSV upstream nguyên bản, phiên bản/checksum, nguồn/điều kiện sử dụng/ngày thu thập nếu có, script/notebook làm sạch và tách section. Nếu không khôi phục được script cũ, tạo một pipeline/version mới từ nguồn thật và mô tả khác biệt; không nhận là tái tạo lịch sử. Cũng cần CV mới có nguồn/lineage và nội dung chuyên môn đã ẩn danh. Chưa tạo CV mới ngoài fixture kiểm thử trong đợt này.

## Hợp đồng import

[Config pilot chạy được](data_configs/pilot_development.json) ánh xạ các cột thực tế. [Template nguồn mới](data_configs/new_sources.template.json) là **mẫu cấu hình**, đường dẫn/cột phải sửa sau khi xem file thật; không mô tả schema upstream đã được xác minh. Đường dẫn CSV được tính tương đối với config.

Mỗi source cần `kind=cv|jd`, namespace ổn định, version thực tế và mapping `columns`. Có thể bỏ mapping của cột chưa có, để công cụ ghi missing; không tạo giá trị thay thế. `defaults` là khai báo nguồn, không phải kết quả extractor. Không đưa nhãn AI hoặc rationale vào mapping feature.

| Trường chuẩn | Hợp đồng |
|---|---|
| `external_id` | ID tài liệu gốc. Thiếu ID dùng hash nội dung làm khóa dự phòng và ghi cờ; không giả lập lịch sử ID. |
| `text` | Nội dung nguồn dùng cho chuẩn hóa. Giữ `text_original`, toàn bộ `raw_row` và file nguồn nguyên byte. |
| `source_group` | Mã nguồn gốc hồ sơ/người/tài liệu trước biến thể, **không phải tên file CSV chung cho mọi CV**. Dùng cùng mã cho bản sửa/ẩn danh/dịch của một nguồn, kể cả khi xuất từ nhiều file. |
| `template_group` | Họ template/generator của CV synthetic. Biến thể cùng khung phải cùng họ. Không đặt mỗi biến thể một mã để vượt kiểm tra. Các mã lineage có phạm vi toàn dataset, cần namespace nhất quán. |
| `role` | Nhóm nhiệm vụ do nguồn/điều phối khai báo, chỉ phục vụ lấy mẫu/phân bố; không tự suy từ title và không dùng làm feature huấn luyện ở bước này. |
| `skills`, `stack` | Chuỗi phân tách bằng `;` hoặc list trong defaults. Chỉ NFKC/casefold/khoảng trắng, chưa có ontology/alias tự động; Java và JavaScript vẫn khác. Không đưa chuỗi phân tách bằng dấu phẩy mà chưa chuyển đổi có nhật ký. |
| `experience` | Ô JSON `{"python backend": 24}`: scope → tháng có căn cứ; CV là thời lượng, JD là ngưỡng cần đối chiếu. Chưa rõ scope/thời lượng thì bỏ khóa. Không tự chuyển kinh nghiệm tổng thành thời gian từng skill; ưu tiên/mơ hồ cần rà trước khi đưa vào metadata này. |
| `is_synthetic` | CV phải khai báo `true`/`false`; trống là chưa biết. CV synthetic thiếu template hoặc mọi CV thiếu source lineage được quarantine. |
| `exposure` | `development` nếu đã xem/dùng để chỉnh cách làm; `prospective` chỉ là ứng viên để chia tập, chưa phải test độc lập. Thiếu thì mặc định development có ghi cờ. |
| `text_scope` | `professional` là xác nhận của bên chuẩn bị rằng text đã xử lý phù hợp; mặc định `unreviewed` → quarantine. Công cụ chưa có parser PDF/PII/section tổng quát. |
| `upstream_text_sha256` | Nếu có, hash văn bản trước chỉnh sửa để đối chiếu nguồn pilot. Không điền bằng suy đoán. |

`source_url`, `collected_at`, `usage_terms` được giữ ở receipt nguồn; thiếu ghi rõ, không bịa ngày hoặc quyền sử dụng. `metadata_status=source_asserted_not_independently_verified` không phải xác nhận chuyên gia. Dữ liệu cá nhân/nguồn hạn chế chỉ đặt ở kho được phép, không commit công khai.

Output mỗi lần là thư mục mới, có `raw/`, `records.jsonl`, `sources.json`, config, group/edge log, pilot anchors, summary và manifest hash mọi artifact + snapshot code. Từ chối ghi vào pilot, ghi đè output hoặc ghi split/cặp bên trong input bất biến. Full output nằm trong `ml_data_runs/` đã Git ignore; các receipt nhỏ trong `docs/ml/reports/` không thay thế full artifact.

ID entity = hash kind/namespace/ID nguồn (hoặc hash text khi thiếu ID); ID record thêm hash nội dung gốc. Đổi thứ tự dòng không đổi ID. Bản sửa cùng ID nguồn giữ chung entity nhưng có record/version mới. Nhiều lần xuất đúng entity/text/metadata được giữ bằng danh sách occurrences; metadata mâu thuẫn bị từ chối để điều phối giải quyết. Source file SHA256 tính trên byte; text hash tính trên chuỗi UTF-8 sau CSV decoding. Hash không là chữ ký xác thực nguồn.

Chuẩn hóa v1 chỉ NFKC, khoảng trắng trên từng dòng và bỏ dòng trắng, giữ nguyên nội dung gốc riêng. Có hash text gốc, text chuẩn hóa và hash casefold phục vụ dedup. Không tự bỏ phần lương/tuổi/marketing hay tái dựng section khi chưa có parser được kiểm chứng. Text rỗng/dưới 40 ký tự bị quarantine có lý do, không xóa nguồn.

## Trùng, gần trùng và bảo vệ pilot

- Trùng text chuẩn hóa/casefold: giữ một record hợp lệ theo ID xác định, record còn lại `exclude_exact_duplicate`, lưu ID bản giữ và tất cả nguồn. Không mất raw hoặc nhãn gốc.
- Gần trùng: Jaccard tập shingle **3 token**, ngưỡng mặc định **0,85**, prefix filtering theo thứ tự token hiếm để tìm cặp đạt ngưỡng. Đây là heuristic lexical cần rà; chưa phát hiện bảo đảm mọi paraphrase/dịch hoặc CV khác bố cục.
- Union các liên kết cùng entity/source/template, trùng chính xác và gần trùng theo tính bắc cầu. Near duplicate vẫn được giữ, chỉ gom cùng group. Quarantine/excluded vẫn tham gia liên kết để không cắt mất cầu nối lineage.
- Luôn đọc và đóng băng anchors pilot từ repo. Bảo vệ theo ID, text gốc/chuẩn hóa/gần trùng, hash JD trước chỉnh sửa. Nhóm nối tới pilot hoặc bất kỳ mẫu `development` nào đều development. Không có cờ bỏ qua pilot trong CLI.

Pilot config gom sáu CV vào một họ template bảo thủ. Lần chạy thật có 51 nhóm (50 JD + 1 họ CV); **cả 51 nhóm đều development**. Không coi con số này là phát hiện 6 CV trùng nội dung.

Khi khôi phục upstream, cần rà source URL, cross-posting và các bản sửa sâu của pilot, vì heuristic/ID không đảm bảo nhận ra mọi trường hợp. Threshold, mapping và version phải được khóa trước split/thí nghiệm; không nới chúng chỉ để lấy thêm test.

## Hai protocol split

| Mode | CV | JD | Kết luận có thể đánh giá về sau |
|---|---|---|---|
| `known-jd` | Nhóm CV disjoint giữa train/validation/test | Kho JD prospective dùng chung, partition `shared`; pilot/development không vào kho này | CV mới trên kho JD đã biết qua train; không kết luận tổng quát hóa JD mới |
| `new-both` | Nhóm CV disjoint | Nhóm JD disjoint tương ứng train/validation/test | Cả CV và JD mới; ít dữ liệu hơn cho mỗi catalog |

Không dùng chung cặp/nhãn giữa hai protocol rồi báo như cùng phép thử. Giữ pilot ở `development` trong cả hai, không dùng cho các cặp train/validation/test mới. `excluded` không tham gia bất kỳ catalog nào.

Seed mặc định `20261113`, tỷ lệ nhóm `0.6/0.2/0.2`. Thuật toán sắp group theo hash(seed, kind, group), giữ tối thiểu một group mỗi partition nếu có ít nhất ba group, phân phần còn lại theo largest remainder. **Tỷ lệ áp cho nhóm, không bảo đảm tỷ lệ số CV/JD hoặc stratification theo nghề.** `distributions.json` và report ghi phân bố thực tế; phải rà mất cân bằng nghề/kinh nghiệm/nguồn trước khóa split, không chỉnh theo kết quả model/test.

Nếu thiếu nhóm hoặc <5 JD cho một catalog, vẫn ghi manifest/report để thấy trạng thái thiếu, `partition_ready=false`; không bẻ nhỏ họ template để lấp partition. `partition_ready=true` chỉ xác nhận điều kiện kỹ thuật tối thiểu, không bảo đảm đủ kích thước thống kê. `final_test_ready=false` vì bước này không có nhãn được xác minh.

`audit` xác minh checksum, tính lại nhóm từ text/lineage/pilot anchors, tái tạo seed/mode, kiểm các nhóm giao partition, mẫu excluded và phát tán pilot. Không xác minh được một người gán sai source_group hoặc cố ý thay provenance. Final-test labels sau này cần kho/quyền truy cập riêng; thư mục local tách biệt không tự tạo sự độc lập.

## Lấy mẫu sau split

`sample --partition train --strategy mixed` lấy trước mẫu ngẫu nhiên đều không hoàn lại từ toàn catalog train hợp lệ; sau đó lấy hard candidates còn lại, không lặp cặp:

1. Có skill chung, khác role có khai báo.
2. Cùng role/có skill chung nhưng stack khai báo không giao nhau.
3. JD yêu cầu số tháng lớn hơn CV ở scope cả hai có dữ kiện.

Mặc định 3 random + tối đa 2 mỗi loại khó/CV. Nếu metadata hoặc ứng viên thiếu, ghi `shortages`, không tự bịa scope/skill hay lấp bằng nhãn 0. Chưa dùng BM25/E5 để mining; `mining_model_version=null`. Heuristic chỉ là lý do lấy mẫu, không kết luận phù hợp.

`pairs.csv` có ID/version/text, `label_status=unlabeled`; relevance/origin/reviewer/evidence/rationale **trống**. Lý do chọn/flags nằm riêng trong `coordinator/selection.json`, không đưa vào phiếu chấm. Đây là schema cặp Mốc 2, chưa phải phiếu A/B của CLI `annotation.py`; chưa nối hay tự triển khai vòng hai reviewer.

Validation/test chỉ cho `--strategy census`: toàn bộ tích CV × catalog đã khóa. Vượt `--max-pairs` thì dừng, không cắt ngầm. Cặp train được lấy mẫu không phải denominator Recall@5 toàn kho; cặp chưa chấm trong census vẫn không phải 0. Chỉ có thể tính ranking metric đúng phạm vi sau khi có nhãn phù hợp và độ phủ đã ghi nhận.

## Kế hoạch mở rộng — mục tiêu, chưa phải dữ liệu đã có

Đề xuất một vòng **120 CV synthetic mới + 360 JD nguồn thật được phép dùng**, ngoài pilot. Bắt đầu lô nhập nhỏ 12–24 CV và 60–90 JD để kiểm parser/lineage, không tạo nhãn kèm hay chạy model. Số lượng mục tiêu không chứng minh đủ lực thống kê hoặc annotation.

| Nhóm nhiệm vụ | CV mục tiêu | JD mục tiêu | Tình huống khó cần phủ |
|---|---:|---:|---|
| Backend Python | 20 | 60 | Django/FastAPI/Odoo; Python chung với phân tích/QA |
| Backend Java | 20 | 60 | Spring, tích hợp; Java/JavaScript, nhiệm vụ frontend |
| Frontend | 20 | 60 | React/Vue/Angular; React/React Native |
| DevOps/Cloud | 20 | 60 | Vận hành thực tế so với backend chỉ biết Docker; AWS/Azure |
| QA/Testing | 20 | 60 | Manual/automation, web/API/performance |
| Data Analyst | 20 | 60 | SQL/BI/KPI so với Python backend và data engineering |

Mỗi nhóm CV dự kiến 4 hồ sơ cho từng dải kinh nghiệm nghề có bằng chứng: 0–11, 12–23, 24–47, ≥48 tháng và chưa đủ dữ kiện. Không áp dải kinh nghiệm nghề cho mọi skill. JD phân tầng tương ứng, thêm yêu cầu ưu tiên, thực tập/bán thời gian, scope chồng nhau, khoảng thời gian mơ hồ và yêu cầu mâu thuẫn. Cố gắng nhiều nguồn/thời điểm mỗi nhóm; không tự đổi nguồn để đạt quota nếu dữ liệu không có.

Viết hồ sơ nghề độc lập với JD đích, lưu `is_synthetic=true`, source/template/generator version và lịch sử biến thể. Có văn bản ngắn/dài, Việt/Anh, nhiệm vụ thực tế và thiếu bằng chứng; không chỉ đổi tên từ sáu CV cũ. Mọi biến thể cùng gốc/template ở cùng partition. Tài liệu PDF/đa cột là hướng extraction tiếp theo, công cụ hiện nhận CSV text.

Với `new-both`, mục tiêu gần 72/24/24 CV và 216/72/72 JD trước ràng buộc group, **không phải output được bảo đảm**. Với `known-jd`, toàn bộ 360 JD eligible có thể dùng chung. Chọn một protocol chính trước thử model và báo cáo riêng protocol phụ. Chưa tạo final-test labels; khi quay lại gán nhãn phải thống nhất rubric/provenance/độc lập phù hợp, không đổi pilot AI thành gold.

## PowerShell

Chạy từ repo; công cụ chỉ dùng thư viện chuẩn Python, không cần môi trường ML/mạng/Docker. Dùng run ID mới mỗi lần:

```powershell
Set-Location D:\JobApply
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$base = ".\ml_data_runs\$runId"
python -m ml_data inventory --output "$base\inventory"
if ($LASTEXITCODE -ne 0) { throw 'Inventory failed' }
python -m ml_data ingest --config .\docs\ml\data_configs\pilot_development.json --output "$base\pilot"
if ($LASTEXITCODE -ne 0) { throw 'Import failed' }
python -m ml_data split --dataset "$base\pilot" --output "$base\pilot_split" --mode known-jd --seed 20261113
python -m ml_data audit --dataset "$base\pilot" --split "$base\pilot_split"
```

Kết quả mong đợi với dữ liệu hiện có: 6 CV/50 JD development, leakage check pass, `partition_ready=false`. **Không chạy sample/train trên pilot split này**; CLI sẽ từ chối vì không có CV/JD eligible cho train.

Sau khi đã có nguồn mới thật và config đã sửa (ví dụ đặt `data/sources_v1.json`, các path tương đối với file đó):

```powershell
$sourceConfig = '.\data\sources_v1.json'
python -m ml_data ingest --config $sourceConfig --output "$base\expanded"
if ($LASTEXITCODE -ne 0) { throw 'Import failed; inspect missing files/schema' }
python -m ml_data split --dataset "$base\expanded" --output "$base\split" --mode new-both --seed 20261113 --ratios 0.6 0.2 0.2
if ($LASTEXITCODE -ne 0) { throw 'Split failed' }
python -m ml_data audit --dataset "$base\expanded" --split "$base\split"
if ($LASTEXITCODE -ne 0) { throw 'Leakage audit failed' }
Get-Content -Raw "$base\split\leakage_report.json"
Get-Content -Raw "$base\split\distributions.json"
# Rà readiness/phân bố, khóa manifest rồi mới tạo cặp.
python -m ml_data sample --dataset "$base\expanded" --split "$base\split" --output "$base\train_pairs" --partition train --strategy mixed --seed 20261113 --random-per-cv 3 --hard-per-type 2
python -m ml_data sample --dataset "$base\expanded" --split "$base\split" --output "$base\validation_pairs" --partition validation --strategy census
python -m ml_data sample --dataset "$base\expanded" --split "$base\split" --output "$base\test_pairs" --partition test --strategy census
python -m ml_data verify --artifact "$base\train_pairs"
```

Lệnh này chuẩn bị **cặp chưa chấm**, không cho phép train trên ô trống. Không có lệnh nhập JD vào app, không thay API/UI, migrations hay VM `192.168.123.136`.
