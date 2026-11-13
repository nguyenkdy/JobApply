# Biên bản kiểm tra JobApply

## ML data preparation, upstream v2 & synthetic CV preview — 13/11/2026

**50 test unittest đạt trong 29,726 giây** trên Windows ML CPython 3.14.3: 11 baseline, 7 recommendation, 16 data pipeline, 10 upstream và 6 synthetic expansion (32 test chỉ dùng thư viện chuẩn chạy trong ~12 giây không cần gói ML). Test upstream và synthetic expansion bao phủ schema 11/25/23 cột thực tế, trạng thái `sections_found/FALSE/FALSE`, cờ mâu thuẫn/JSON sai/trạng thái lạ, ranh giới 79/80 ký tự sau chuẩn hóa, lỗi UTF-8/`#NAME?`, lineage rỗng hoặc sai URL/hash, tách tag nguồn Data Analyst với dấu hiệu chức danh, kiểm tra bằng chứng nguyên văn + offset của 60 CV giả lập, giữ `experience_json={}` cho 10 CV thiếu thời lượng, cấm thông tin nhạy cảm/PII, bất biến toàn bộ 3.062 JD khi import kết hợp, chống rò rỉ nhóm `template_group` trong preview split `known-jd` và từ chối chạy trên upstream run bị sửa.

Hai CLI run `upstream-observation-v2` hoàn tất ở `ml_data_runs/20261113_upstream_v2_01` và `_02` (**51/51 file giống byte**). Hai lần chạy `python -m ml_data synthetic-cvs` (`16/16` file giống byte) và hai lần chạy `python -m ml_data expand-preview` (`65/65` file giống byte) trên `20261113_upstream_v2_01` tạo 60 CV giả lập (12 CV × 5 nghề, 6 họ `template_group`), kết hợp với 3.062 JD v2 (giữ nguyên 888 keep / 65 duplicate / 2.109 quarantine và 154 record trong closure development) và xuất preview split `known-jd` (`30` train / `20` validation / `10` test CV trên `788` JD dùng chung; `90` cặp train ngẫu nhiên + `180` slot hard thiếu metadata JD, `15.760` cặp validation, `7.880` cặp test; `pair_files_created=0`, `labels_created=0`, `final_test_ready=false`). Kiểm tra giữ nguyên byte đạt cho 3 CSV nguồn và toàn bộ 51 file theo dõi trong `jobapply_pilot_v1/`. Chưa tạo nhãn gold, chưa train lại model hay chạy API/UI/Docker/VM.

Ruff cho `ml_data`, `scripts/report-upstream.py`, `tests/ml/` và `git diff --check` đạt. Chi tiết/lệnh/giới hạn: [dataset pipeline](docs/ml/dataset_pipeline.md), [receipt upstream](docs/ml/reports/20261113-data-preparation.json), [danh sách lô JD](docs/ml/reports/20261113-upstream-jd-selection.json), [receipt preview CV + JD](docs/ml/reports/20261113-cv-jd-preview.json).

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
