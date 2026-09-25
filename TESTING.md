# Biên bản kiểm tra JobApply

Ngày kiểm tra: 25/09/2026. Máy phát triển Windows; Python 3.14.3; Node.js portable 22.16.0 trong `.tools/`; Chrome có sẵn. `.tools/`, `.venv/`, file CV/database smoke và kết quả browser được Git ignore.

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

Trước khi thống nhất mô hình VM, bản Compose ban đầu đã qua kiểm tra `config --quiet` bằng CLI portable. **Bản cấu hình VM cuối chỉ được kiểm tra tĩnh/YAML trên máy này; không chạy Docker Compose thêm sau yêu cầu tách môi trường.** Cần chạy `docker compose config --quiet` trên VM với `.env` thật.

Browser/HTTP smoke local ở trên **không** chứng minh Docker, Nginx, PostgreSQL, network VMware, firewall hoặc volume persistence đã hoạt động. Giao diện được kiểm tra qua Vite; PostgreSQL DDL chỉ compile offline, không kết nối PostgreSQL.

## Chưa chạy — cần VM Linux

- Build các Docker image Linux; `docker compose config --quiet` với cấu hình thực tế.
- Khởi tạo 3 database/user PostgreSQL và migration trên PostgreSQL thật.
- Healthcheck, Nginx `/api` routing, Swagger sau reverse proxy, kết nối service qua Docker DNS.
- Bộ pytest PostgreSQL, bao gồm unique constraint/request đồng thời và transaction lịch sử.
- HTTP workflow qua Nginx/container/PostgreSQL; persistence database/CV qua recreate/restart.
- Truy cập từ máy thật tới `http://<VM_IP>:8080`, Bridged/NAT/firewall/port forwarding.
- Deploy/update script thực thi đầy đủ qua GitHub → VM.

Repository GitHub được người dùng cung cấp sau bước kiểm thử: `https://github.com/nguyenkdy/JobApply.git`; branch triển khai `main`. Chưa có IP/user SSH hoặc quyền vào VM, chưa SSH/deploy. Việc đưa code lên GitHub không thay thế nghiệm thu trên VM.

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
