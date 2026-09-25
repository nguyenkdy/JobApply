#!/bin/sh
# VM gateway test; use the VM's actual IP to test its network binding.
set -eu
base_url=${1:-http://127.0.0.1:8080}
base_url=${base_url%/}
case "$base_url" in
  http://*|https://*) ;;
  *) echo 'URL phải bắt đầu bằng http:// hoặc https://' >&2; exit 2 ;;
esac
command -v curl >/dev/null || { echo 'Thiếu curl trên VM.' >&2; exit 1; }
for endpoint in / /health /api/account/health /api/job/health /api/application/health '/api/job/jobs?limit=1'; do
  if ! body=$(curl --fail --silent --show-error --connect-timeout 3 --max-time 20 "$base_url$endpoint"); then
    echo "FAIL: $endpoint" >&2
    exit 1
  fi
  case "$endpoint" in
    /) case "$body" in *'id="root"'*) ;; *) echo 'FAIL: Không tìm thấy frontend React.' >&2; exit 1 ;; esac ;;
    /health) [ "$body" = ok ] || { echo 'FAIL: Gateway health không hợp lệ.' >&2; exit 1; } ;;
    */health) case "$body" in *'"status":"ok"'*) ;; *) echo "FAIL: $endpoint không healthy." >&2; exit 1 ;; esac ;;
    *) case "$body" in '['*) ;; *) echo 'FAIL: Jobs API không trả JSON array.' >&2; exit 1 ;; esac ;;
  esac
  echo "PASS: $endpoint"
done
# Protected endpoints must reject anonymous requests, not merely respond with 200.
for endpoint in /api/account/me /api/account/cvs /api/job/jobs/mine /api/application/applications; do
  code=$(curl --silent --show-error --connect-timeout 3 --max-time 20 -o /dev/null -w '%{http_code}' "$base_url$endpoint") || exit 1
  if [ "$code" != 401 ]; then
    echo "FAIL: $endpoint trả HTTP $code, yêu cầu 401 khi chưa đăng nhập." >&2
    exit 1
  fi
  echo "PASS: $endpoint bảo vệ bằng đăng nhập"
done
echo 'Smoke endpoint hoàn tất. Kiểm tra riêng truy cập IP VM từ máy thật và luồng nghiệp vụ bằng trình duyệt.'
