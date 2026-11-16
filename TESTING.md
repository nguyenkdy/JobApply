# Kiểm thử

## Chuẩn bị 120 CV và luật nhãn mở rộng — 16/11/2026

**110/110 test đạt**, 69,220 giây. Bổ sung 2 test giữ ID/lineage và partition cũ, 13 test ngữ nghĩa luật nhãn: thiếu skill không phải phủ định; khác nghề không tự nhãn 0; unknown/outside scope; ưu tiên và AND/OR; scope tháng và ngưỡng nghiêm ngặt; câu điều kiện; offset theo schema JD thực; census toàn catalog và chặn metric khi thiếu nhãn. Dùng fixture riêng, không dùng CV holdout để sửa cách chấm.

Hai run intake v7 có **99/99 file giống byte**, hai run nhãn v1 có **32/32 file giống byte**. `check-expanded-labels` dựng lại facts từ văn bản/receipt, tái tính quyết định cho 48.284 cặp, kiểm lưới train/census, partition, version/hash, evidence và tổng hợp. Xác minh 54 file nguồn/pilot, sáu run lịch sử và việc lô v5 vẫn bị xóa. Ruff đạt; `git diff --check` sạch. Test đạt chỉ chứng minh các hợp đồng kỹ thuật, không chứng nhận nhãn đúng hoặc dataset sẵn sàng train. [Báo cáo và giới hạn thực tế](docs/ml/expanded_preparation.md).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data scripts/report-expanded-preparation.py tests/ml/test_intake.py tests/ml/test_expanded_labels.py
if ($LASTEXITCODE -ne 0) { throw 'Expanded preparation lint failed' }
```

## Tiếp nhận CV viết riêng v6 — 16/11/2026

**95/95 test đạt**, 71,911 giây. Tám test mới trong `tests/ml/test_intake.py` dùng fixture riêng: từ chối slot/shared-template, giữ nguyên text và evidence, không xóa ancestry khi đổi ngân hàng, từ chối parent thiếu ancestry/JD đích, nguồn trùng/skill không có bằng chứng, giữ cờ JD và protocol known-JD, không suy nhãn từ tên nghề và không coi lexical similarity là chứng nhận độc lập.

Hai run `_02`/`_03` có **80/80 file giống byte**. `check-cv-intake` dựng lại metadata/evidence, nhóm, assignment theo seed và các cặp lấy mẫu; kiểm nguyên văn/hash và nhãn trống. Cả 30 CV qua gate khai báo, 788 JD được giữ; preview 10/10/10 và 165 cặp train. Kiểm thử đạt không chứng minh độ chính xác nhãn hoặc chất lượng ML. Ruff đạt cho module/CLI, script báo cáo và test mới; nguồn/pilot giữ nguyên. [Báo cáo từ run](docs/ml/authored_cv_intake.md).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data/intake.py ml_data/__main__.py scripts/report-cv-intake.py tests/ml/test_intake.py
if ($LASTEXITCODE -ne 0) { throw 'CV intake lint failed' }
```

## Sau xóa lô 200 CV v5 — 16/11/2026

**87/87 test còn dùng đạt**, 35,238 giây. Đã gỡ tám test và công cụ riêng của lô bị loại; kết quả 95 test trước đây thuộc phiên bản trước dọn dẹp. Ruff đạt cho `ml_data`, hai script báo cáo JD và test catalog/refinement; `git diff --check` sạch. Đã xác minh 54 hash nguồn/pilot và manifest đầy đủ của sáu run được giữ nguyên; tám thư mục đã xóa không còn tồn tại. Giữ các test metadata, lineage và chốt chặn nhãn của pipeline còn dùng. [Phạm vi xóa và kiểm chứng](docs/ml/retired_expanded_cv_cleanup.md).

## Metadata catalog v4 — 16/11/2026

**87/87 test đạt**, 74,565 giây; tám test mới ở `tests/ml/test_refinement.py` kiểm các dạng chức danh thực tế, bảo toàn xung đột/generic, không suy nghề từ một công nghệ, tách optional/core, evidence theo schema canonical, bảo toàn duration/unknown và chặn bộ luật nhãn cũ trên taxonomy mới. Sau chỉnh chẩn đoán `3+ years`, chạy lại đủ tám test mới đạt (0,097 giây). Ruff đạt cho module/CLI/label guard, script báo cáo và test mới. Không chạy lại model hoặc benchmark pilot.

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data/refinement.py ml_data/label_rules.py ml_data/__main__.py scripts/report-jd-refinement.py tests/ml/test_refinement.py
if ($LASTEXITCODE -ne 0) { throw 'Metadata lint failed' }
```

Hai run hiện hành là `20261116_jd_metadata_v4_03` và `_04`; báo cáo được sinh sau kiểm manifest và so sánh toàn bộ file. `_01`/`_02` là snapshot trung gian trước sửa quy tắc và kế hoạch, giữ nguyên để truy vết, không dùng làm đầu vào tiếp theo. [Báo cáo kiểm chứng](docs/ml/jd_metadata_refinement.md).

## Mở rộng toàn bộ catalog JD — 16/11/2026

**79/79 test đạt**, 70,415 giây. Năm test mới ở `tests/ml/test_catalogue.py` kiểm giữ mọi nghề/unknown, không sửa đầu vào, giữ nhóm gần trùng và lịch sử benchmark, từ chối ID trùng/JD không hợp lệ/leakage development, tính khối lượng thiếu metadata mà không tạo nhãn, kiểm evidence theo offset và nội dung nguồn. Ruff đạt cho module/CLI, script báo cáo và test mới.

Hai lần `expand-jd-catalogue` trên dữ liệu thật có **73/73 file giống byte**: 3.062 record nguồn, 788 JD catalog, 698 nhóm. Đã xác minh manifest, hash ba CSV nguồn, 51 file pilot và hai run chuẩn bị/Bước 4 không đổi. Không chạy training/scoring mới hoặc API/UI/Docker/VM. [Báo cáo sinh từ run](docs/ml/jd_catalogue_expansion.md).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data/catalogue.py ml_data/__main__.py scripts/report-jd-catalogue.py tests/ml/test_catalogue.py
if ($LASTEXITCODE -ne 0) { throw 'Catalogue lint failed' }
```

## Bước 4 — 14/11/2026

**74/74 test đạt**, 55,301 giây. Mười test mới ở `tests/ml/test_step4.py` kiểm metric có mẫu số undefined, tie theo ID, scaler chỉ fit train, lựa chọn không dùng baseline sinh nhãn, scope/cận kinh nghiệm, đủ lưới cặp, allowlist thông tin cá nhân, suy luận gói và từ chối artifact bị sửa trước deserialize. `pip check` đạt; Ruff đạt cho phạm vi ML mới và sửa đổi.

Đã chạy thực tế E5-base trên CPU, fit chín LR (ba nhóm feature × ba C), chọn trên validation rồi chấm test theo protocol đã ghi trước. Gói release suy luận trên hai CV validation giữ nguyên Top 5 và điểm (max delta 0); encode lặp hai CV train lệch tối đa 2,645e-7 ≤ 1e-6. Probe metadata cá nhân đạt trong phạm vi cấu trúc, không phải kiểm chứng fairness/PDF đầu cuối. Run chuẩn bị, ba CSV gốc, 51 file pilot không đổi; không chạy API/UI/Docker/VM. [Báo cáo từ run](docs/ml/step4_results.md).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data ml_experiment scripts/report-pretraining.py scripts/fetch-step4-encoder.py scripts/release-step4-model.py scripts/report-step4.py tests/ml/test_benchmark_prep.py tests/ml/test_automatic_labels.py tests/ml/test_pretraining.py tests/ml/test_step4.py
if ($LASTEXITCODE -ne 0) { throw 'ML lint failed' }
```

## Sau dọn công cụ CV v2 — 14/11/2026

**64/64 test đạt**, 34,589 giây. Ruff đạt trong phạm vi lệnh dưới; `git diff --check` sạch. Test lineage dùng fixture sáu hồ sơ thay bộ 60 CV v2; các kiểm tra chống trùng, ancestry, unknown và bảo toàn JD vẫn chạy. `check-pretraining` với run v3 hiện hành đạt **22/22 điều kiện**, đủ 1.500/750/750 cặp như trước.

Đã xác minh manifest của bốn run đầu vào và hai run v3, cùng hash ba CSV nguồn/51 file pilot; không thay đổi dữ liệu. Đã kiểm tra CLI không còn lệnh dựng benchmark v2 và không còn import tới module/assets đã xóa. Không chạy lại chuẩn bị dữ liệu hoặc Bước 4. [Chi tiết dọn dẹp](docs/ml/retired_cv_cleanup.md).

## Điều kiện trước Bước 4 — 14/11/2026

**64/64 test unittest đạt**, 71,875 giây, trên môi trường ML Windows Python 3.14.3. Năm test mới kiểm tra CV/evidence tái tạo, mọi ngưỡng kinh nghiệm đúng scope và cận nghiêm ngặt, kỹ năng đã biết khác nhau so với metadata thiếu, AND/OR/ưu tiên và luồng chuẩn bị đầy đủ. Test cuối từ chối lưới CV×JD thiếu cặp dù đã cập nhật checksum nhất quán; không chỉ kiểm tổng số hàng.

Hai lần `prepare-experiment` trên dữ liệu thật có **302/302 file giống byte**; `check-pretraining` đạt đủ 22 gate. Ba CSV nguồn, 51 file pilot và bốn run đầu vào lịch sử không đổi. Kết quả hiện hành: 60 CV mới, 12 nhóm, split 30/15/15, đủ 3.000 nhãn số tự động. Lô v2 cũ vẫn development. [Báo cáo từ run](docs/ml/pretraining_handoff.md).

Ruff đạt với phạm vi dưới. Không chạy scoring/training/metric benchmark mới; unittest dùng fixture tạm. Không chạy API/UI/Docker/VM.

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m unittest discover -s tests/ml -v
if ($LASTEXITCODE -ne 0) { throw 'ML tests failed' }
& .\.venv\Scripts\python.exe -m ruff check ml_data scripts/report-pretraining.py tests/ml/test_benchmark_prep.py tests/ml/test_automatic_labels.py tests/ml/test_pretraining.py
if ($LASTEXITCODE -ne 0) { throw 'ML lint failed' }
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data check-pretraining --artifact .\ml_data_runs\20261114_pretraining_v3_01
if ($LASTEXITCODE -ne 0) { throw 'Pretraining checks failed' }
```

## Lịch sử kiểm toán benchmark v2 — 14/11/2026

Các tên công cụ ở phần lịch sử bên dưới mô tả lượt kiểm toán trước dọn dẹp; `prepare-benchmark`, `training-readiness` và `report-benchmark-audit.py` đã được gỡ. Dùng `check-pretraining` cho lô hiện hành.

**59/59 test unittest đạt** trên Windows ML Python 3.14.3. Bao phủ lineage v1→v2 nối thành một nhóm, giữ nguồn/pilot, scope kinh nghiệm, cận nghiêm ngặt, unknown không thành 0, không coi thực tập/dự án là thời gian nghề, ID trùng và evidence không đúng nguồn. Không còn test yêu cầu calibration/người review hoặc ép CV v2 đủ ba partition bằng cách đổi họ.

Ruff đạt cho `ml_data`, `scripts/report-benchmark-audit.py`, `tests/ml/test_benchmark_prep.py` và `tests/ml/test_automatic_labels.py`. Quét rộng `tests/ml` còn 20 lỗi style có sẵn ở `test_baseline.py`/`test_recommend_run.py` (E402/E702); không sửa các phần baseline ngoài phạm vi.

Đã chạy kiểm toán dữ liệu thật vào thư mục run mới, giữ nguyên nguồn và benchmark cũ. Cổng `training-readiness` phải trả exit 1 với **lô v2 cũ** vì chỉ có một nhóm CV sau khi giữ đủ ancestry, thiếu validation/test và còn nhãn thiếu bằng chứng. Đây là lỗi điều kiện dữ liệu, không phải chờ người chấm. Không train, không đóng gói model hoặc chạy API/UI/Docker/VM. [Báo cáo](docs/ml/benchmark_audit.md).

Kết quả 55 test và các run chuẩn bị cũ là lịch sử; “tái tạo giống byte” không chứng minh split độc lập hoặc nhãn đúng ngữ nghĩa. Kiểm toán mới thay thế kết luận sẵn sàng huấn luyện của các bản chuẩn bị cũ.

## ML baseline — 12/11/2026

Mốc 0 chạy offline trên Windows bằng môi trường ML riêng: **11 test unittest đạt**, encode E5 revision/hash cố định và train lại đầy đủ. Hai run `_02`/`_03` có bảy bảng đầu ra giống byte; hash 33 artifact gốc giữ nguyên. **4 test cấu hình app đạt**; module ML skip trong môi trường backend không có dependencies ML, và đã chạy riêng đủ 11 test bằng `.venv-embedding`. Chi tiết số đo, lệnh, sai khác điểm với lịch sử và phần cần chuyên gia: [docs/ml/baseline.md](docs/ml/baseline.md). Không chạy lại Docker, workflow app hay E2E trong đợt này.

Các biên bản bên dưới là lịch sử kiểm thử ứng dụng, không phải kết quả chạy lại ngày 12/11.

Kiểm tra local ngày 25/09/2026; cập nhật kết quả VM ngày 26/09/2026. Máy phát triển Windows; Python 3.14.3; Node.js portable 22.16.0 trong `.tools/`; Chrome có sẵn. `.tools/`, `.venv/`, file CV/database smoke và kết quả browser được Git ignore.

## Đã chạy trên máy VS Code

| Kiểm tra | Kết quả và phạm vi |
|---|---|
| `python -m pytest -q` | **26 passed**; 3 database SQLite tạm riêng, Alembic thật, test HTTP qua FastAPI TestClient; bao gồm ACL, unique race, trạng thái, CV bất biến, dependency/DB failure, cấu hình VM và compile DDL PostgreSQL offline |
| `python -m ruff check shared services scripts tests` | **Pass** |
| `python -m compileall -q shared services scripts tests` | **Pass** |
| `npm ci` | **Pass**, lockfile đồng bộ; báo cáo npm lúc cài: 0 vulnerabilities |
| `npm run build` | **Pass**, Vite tạo `frontend/dist` |
| `npm test` | **4 passed**, API client/validation/401/network failure |
| `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` | **2 passed**, luồng recruiter → company → job → candidate → CV → application → download → review và tìm kiếm/mobile 390px |
| `python scripts/smoke-workflow.py --base-url http://127.0.0.1:5173` | **PASS**, HTTP thật qua Vite proxy, 3 Uvicorn process và SQLite smoke; cả nộp trùng, tải CV, review, lịch sử, rút/đóng job |
| Seed chạy hai lần | Cả hai lần kết thúc thành công, không lỗi trùng email/company/job; seed có nhánh tìm dữ liệu đã có |
| Git Bash `-n` trên 3 script `.sh` | **Pass** cú pháp, không thực thi triển khai; test kiểm tra LF cũng pass |
| Kiểm tra Git ignore | `.env`, virtualenv, node_modules, dist, CV và DB smoke được loại trừ |
| Quan sát ảnh UI | Đã xem ảnh desktop và mobile của Playwright; không tràn chiều ngang ở 390px |

Backend có 1 cảnh báo deprecation từ Starlette về adapter httpx của TestClient; không có test fail. TestClient hiện dùng adapter httpx phù hợp với test transport. Không thay đổi runtime HTTP production vì cảnh báo của test tooling.

Các lệnh Docker trong đợt nghiệm thu bên dưới chỉ chạy trên VM. Máy VS Code chạy Git và các kiểm thử có runtime phù hợp; Chrome trên máy thật truy cập IP VM.

Kết quả local ở bảng trên dùng Vite/SQLite; kết quả VM bên dưới dùng Nginx, các container Python và PostgreSQL thật. Hai phạm vi được ghi riêng.

## Đã chạy trên VM Linux — 26/09/2026

VM Ubuntu 24.04, Docker Engine 29.8.1, Docker Compose 5.5.1. Repository `nguyenkdy/JobApply`, branch `main`; mã ứng dụng triển khai từ commit `587602a` (các commit sau cập nhật test/biên bản không thay đổi mã chạy).

| Kiểm tra | Kết quả |
|---|---|
| Build 4 image ứng dụng Linux, `deploy-vm.sh first` | **Pass**; PostgreSQL được khởi động trước, 3 migration hoàn tất rồi khởi động API/gateway |
| `docker compose config --quiet` với `.env` riêng VM | **Pass**; secrets không được in hoặc commit |
| Sau khi người dùng tắt/bật lại VM | Cả **5 container tự khởi động và healthy**, PostgreSQL/CV vẫn dùng named volumes hiện có |
| `scripts/smoke-vm.sh http://192.168.123.136:8080` | **Pass** toàn bộ endpoint, bao gồm kiểm tra anonymous bị trả 401 |
| HTTP từ máy thật tới IP VM | Trang React, gateway và health của cả ba API đều trả **200** |
| Seed riêng trên VM | **Pass**; 8 tin Published thuộc 3 công ty; hai tài khoản demo Candidate/Recruiter đều đăng nhập 200 |
| `docker compose exec -T account python scripts/smoke-workflow.py --base-url http://frontend` | **PASS**, luồng nghiệp vụ HTTP thật qua Nginx/Docker DNS/PostgreSQL, bao gồm tải CV và nộp trùng |
| `docker compose --profile test run --build --rm tests` | **26 passed**, 1 cảnh báo deprecation TestClient; database test độc lập được teardown, không reset database ứng dụng |
| Chrome từ máy thật, `E2E_BASE_URL=http://192.168.123.136:8080` | **2 passed** sau khi sửa test chờ đúng thông báo/loading và trạng thái radio sau điều hướng bất đồng bộ |

Test browser tạo tài khoản/công ty giả; job của ca thành công được đóng sau kiểm tra để không xuất hiện trong tìm kiếm công khai. Workflow smoke cũng rút application và đóng job test, giữ lịch sử để chẩn đoán. Không xóa CV/database hoặc reset volume trong quá trình kiểm tra.

Chưa kiểm chứng riêng: hiển thị Swagger UI sau proxy; giữ nguyên nội dung CV/application qua một lần recreate sau khi nộp (CV demo được thêm sau lần reboot nói trên); quy trình update có migration schema mới; giới hạn truy cập từ các máy ngoài mạng tin cậy. Kết nối từ máy thật tới VM đã hoạt động, nhưng không suy ra toàn bộ chính sách firewall/NAT đã được kiểm toán.

## Lệnh nghiệm thu trên VM

Sau khi clone đúng repo/branch và tạo `.env` riêng theo `docs/deploy-vm.md`:

```sh
docker compose config --quiet
sh scripts/deploy-vm.sh first
docker compose --profile tools run --build --rm seed
sh scripts/smoke-vm.sh http://<VM_IP>:8080
docker compose exec -T account python scripts/smoke-workflow.py --base-url http://frontend
docker compose --profile test run --build --rm tests
docker compose ps
```

Kiểm tra persistence: nộp một hồ sơ và ghi nhận CV, `docker compose restart`, đăng nhập lại rồi tải đúng CV cũ, kiểm tra application/lịch sử vẫn còn. Có thể kiểm tra thêm `up -d --force-recreate` trong VM demo; **không dùng `down --volumes`** cho kiểm tra giữ dữ liệu.

Trên máy thật: `Test-NetConnection <VM_IP> -Port 8080`, mở browser và thực hiện kịch bản hai tài khoản trong README. Chỉ đánh dấu nghiệm thu VM thành công sau khi các bước này thực sự chạy qua.
