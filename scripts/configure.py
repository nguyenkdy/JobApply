"""Create local .env with random secrets. Never overwrite an existing file."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env đã tồn tại; giữ nguyên cấu hình hiện có.")
values = {
    name: secrets.token_hex(24)
    for name in ("POSTGRES_PASSWORD", "ACCOUNT_DB_PASSWORD", "JOB_DB_PASSWORD", "APPLICATION_DB_PASSWORD", "JWT_SECRET")
}
lines = (root / ".env.example").read_text(encoding="utf-8").splitlines()
with target.open("x", encoding="utf-8") as output:
    for line in lines:
        key = line.split("=", 1)[0]
        output.write(f"{key}={values[key]}\n" if key in values else line + "\n")
print("Đã tạo .env với secrets ngẫu nhiên. Không commit hoặc chia sẻ file này.")
