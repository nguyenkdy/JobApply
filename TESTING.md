# Biên bản kiểm tra JobApply

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
