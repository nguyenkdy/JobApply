#!/bin/sh
# Run on the Linux VM only: sh scripts/deploy-vm.sh first|update
set -eu
# Parse the function completely before running git pull, which may update this file.
main() {
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mode=${1:-}
case "$mode" in
  first|update) ;;
  *) echo 'Cách dùng: sh scripts/deploy-vm.sh first|update' >&2; exit 2 ;;
esac
trap 'echo "Triển khai thất bại. Kiểm tra lỗi ở trên và docker compose logs --tail=100. Không có dữ liệu nào bị reset tự động." >&2' 0
command -v git >/dev/null || { echo 'Thiếu Git.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Thiếu Docker Engine/CLI trên VM.' >&2; exit 1; }
docker compose version >/dev/null || { echo 'Thiếu Docker Compose plugin.' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Không truy cập được Docker Engine; kiểm tra daemon và quyền user trên VM.' >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null
if [ -n "$(git status --porcelain)" ]; then
  echo 'Working tree không sạch. Dừng để bảo toàn thay đổi local; tự kiểm tra git status và xử lý trước khi triển khai.' >&2
  exit 1
fi
if [ ! -f .env ]; then
  echo 'Thiếu .env trên VM. Tạo từ .env.example và thay toàn bộ placeholder.' >&2
  exit 1
fi
if grep -q '^\(POSTGRES_PASSWORD\|ACCOUNT_DB_PASSWORD\|JOB_DB_PASSWORD\|APPLICATION_DB_PASSWORD\|JWT_SECRET\)=CHANGE_ME' .env; then
  echo '.env còn placeholder. Điền secrets riêng của VM; không đưa vào Git.' >&2
  exit 1
fi
if [ "$mode" = update ]; then
  git symbolic-ref --quiet --short HEAD >/dev/null || { echo 'Đang ở detached HEAD; checkout branch triển khai trước.' >&2; exit 1; }
  git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 || { echo 'Branch chưa có upstream; xác định đúng remote/branch trước.' >&2; exit 1; }
  git pull --ff-only
fi
docker compose config --quiet
# Build before downtime, so a failed build does not interrupt the running version.
docker compose build account job application frontend
if [ "$mode" = update ]; then
  docker compose stop frontend application job account
fi
docker compose up -d --wait postgres
docker compose run --rm --no-deps account python scripts/migrate.py account
docker compose run --rm --no-deps job python scripts/migrate.py job
docker compose run --rm --no-deps application python scripts/migrate.py application
# API entrypoints repeat upgrade head safely; seed has a separate tools profile.
docker compose up -d --wait
docker compose ps
trap - 0
echo 'Container đã khởi động healthy. Chạy smoke test và kiểm tra từ máy thật; seed là bước riêng.'
}
main "$@"
