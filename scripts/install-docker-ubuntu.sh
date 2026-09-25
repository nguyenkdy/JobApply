#!/bin/sh
# Run on the Ubuntu VM: sudo sh scripts/install-docker-ubuntu.sh myserver
# Official installation reference: https://docs.docker.com/engine/install/ubuntu/
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo 'Cần chạy bằng sudo trên VM để cài Docker.' >&2
  exit 1
fi
target_user=${1:-${SUDO_USER:-}}
if [ -z "$target_user" ] || [ "$target_user" = root ]; then
  echo 'Chỉ định tài khoản triển khai: sudo sh scripts/install-docker-ubuntu.sh myserver' >&2
  exit 2
fi
id "$target_user" >/dev/null
. /etc/os-release
if [ "$ID" != ubuntu ] || [ "$VERSION_ID" != 24.04 ]; then
  echo 'Script này được chuẩn bị cho Ubuntu 24.04; dừng để kiểm tra distro.' >&2
  exit 1
fi
# Do not remove existing runtimes or their data to work around a package conflict.
for package in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q '^install ok installed$'; then
    echo "Có package có thể xung đột: $package. Dừng để kiểm tra trước khi thay đổi." >&2
    exit 1
  fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=120 update
apt-get -o DPkg::Lock::Timeout=120 install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
key_temp=$(mktemp)
source_temp=$(mktemp)
trap 'rm -f "$key_temp" "$source_temp"' 0
curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 \
  https://download.docker.com/linux/ubuntu/gpg -o "$key_temp"
install -m 0644 "$key_temp" /etc/apt/keyrings/docker.asc
architecture=$(dpkg --print-architecture)
cat > "$source_temp" <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $architecture
Signed-By: /etc/apt/keyrings/docker.asc
EOF
if [ -f /etc/apt/sources.list.d/docker.list ]; then
  echo 'Đã có docker.list; dừng để tránh cấu hình APT trùng.' >&2
  exit 1
fi
if [ -f /etc/apt/sources.list.d/docker.sources ] && ! cmp -s "$source_temp" /etc/apt/sources.list.d/docker.sources; then
  echo 'docker.sources hiện có khác cấu hình dự kiến; dừng để kiểm tra.' >&2
  exit 1
fi
install -m 0644 "$source_temp" /etc/apt/sources.list.d/docker.sources
apt-get -o DPkg::Lock::Timeout=120 update
apt-get -o DPkg::Lock::Timeout=120 install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "$target_user"
docker version --format '{{.Server.Version}}'
docker compose version
docker info --format 'Docker root: {{.DockerRootDir}}'
echo "Cài đặt hoàn tất. Tài khoản $target_user có quyền quản trị Docker trong phiên SSH mới."
echo 'Không thay đổi firewall, không xóa dữ liệu. Tiếp tục triển khai trong phiên SSH mới.'
