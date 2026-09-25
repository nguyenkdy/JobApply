# Triển khai JobApply trên VM Linux (VMware)

Máy VS Code chỉ viết code, quản lý Git và chạy kiểm tra bằng runtime có sẵn. **Không cài hoặc chạy Docker trên máy VS Code.** VM Linux chạy Docker Engine, Compose, Nginx, ba API và PostgreSQL. Trình duyệt máy thật truy cập `http://<VM_IP>:8080`.

Luồng cập nhật: VS Code → commit/push GitHub → SSH VM → kiểm tra working tree → `git pull --ff-only` → build → dừng API ngắn hạn → migrate → chạy lại → kiểm tra.

## Thông tin cần có

- Repository GitHub đã được người dùng xác định: `https://github.com/nguyenkdy/JobApply.git`.
- Branch triển khai: `main`.
- `<VM_IP>`, `<VM_USER>`: IP và user Linux thực tế. Chưa có các thông tin này hoặc quyền SSH thì chưa thể triển khai/xác nhận kết quả trên VM.
- `<HOST_IP>` hoặc `<TRUSTED_SUBNET>`: địa chỉ máy thật/mạng tin cậy được phép truy cập web.

Repository private cần SSH key hoặc phương thức GitHub xác thực hợp lệ **trên VM**. Không đưa access token vào URL lệnh, `.env`, Git hoặc tài liệu.

## Mạng VMware và firewall

Trong VM:

```sh
hostname -I
ip -4 addr
ip route
```

Chọn IPv4 của card mạng VMware đang hoạt động (ví dụ `ens33`), bỏ qua `127.0.0.1`, địa chỉ bridge Docker `172.x` của `docker0`/`br-*`. Dùng IP thực tế đó thay `<VM_IP>`; có thể cần đặt DHCP reservation để IP không đổi giữa các buổi demo.

- **Bridged:** VM nhận IP trong cùng LAN với máy thật. Kiểm tra hai thiết bị có thể kết nối trong LAN, Wi-Fi/AP không bật client isolation.
- **NAT:** kiểm tra máy thật có truy cập trực tiếp subnet VMnet8 và IP VM hay không; nhiều cấu hình VMware cho phép. Nếu không, tạo NAT port forwarding trong Virtual Network Editor → VMnet8 → NAT Settings: TCP host port `8080` → guest `<VM_IP>:8080`. Khi forward qua host, truy cập `http://127.0.0.1:8080` trên máy thật; điểm đích trong VM vẫn là cổng 8080. Chỉ bind forward vào máy thật nếu công cụ hỗ trợ. Nếu cần SSH qua NAT, cấu hình riêng TCP host `2222` → guest `22`, dùng `ssh -p 2222 <VM_USER>@127.0.0.1`.
- Không forward `5432`, `8000`, `8001`, `8002`, `8003`. Compose chỉ publish web. Không dùng `compose.debug.yaml` cho demo qua IP VM.

Kiểm tra trên máy thật (PowerShell):

```powershell
Test-NetConnection <VM_IP> -Port 22
Test-NetConnection <VM_IP> -Port 8080
curl.exe -f http://<VM_IP>:8080/health
```

ICMP/ping có thể bị chặn dù TCP vẫn hoạt động; ưu tiên kết quả TCP/HTTP. Trước khi triển khai, cổng 8080 chưa mở là bình thường.

Chỉ cho phép SSH/web từ máy thật hoặc subnet tin cậy. Ví dụ nếu VM dùng UFW:

```sh
sudo ufw allow from <HOST_IP> to any port 22 proto tcp
sudo ufw allow from <HOST_IP> to any port 8080 proto tcp
sudo ufw status verbose
```

Không tắt toàn bộ firewall. Giữ quyền SSH hiện có trước khi thay rule. Nếu dùng firewalld, tạo rule giới hạn nguồn tương đương trên zone đang hoạt động.

**Lưu ý Docker trên Linux:** cổng container publish có thể đi qua NAT/FORWARD và bỏ qua rule UFW thông thường. Không coi `ufw allow/deny` là bằng chứng cổng Docker đã bị giới hạn. Với iptables backend mặc định, quản trị viên có thể áp dụng rule `DOCKER-USER` giới hạn nguồn cho cổng 8080 (sau khi kiểm tra rule hiện có, không flush chain):

```sh
sudo iptables -I DOCKER-USER 1 -i <VM_INTERFACE> -p tcp -s <HOST_IP>/32 -m conntrack --ctdir ORIGINAL --ctorigdstport 8080 -j ACCEPT
sudo iptables -I DOCKER-USER 2 -i <VM_INTERFACE> -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 8080 -j DROP
sudo iptables -L DOCKER-USER -n --line-numbers
```

Thay `<VM_INTERFACE>` bằng card VM nhận lưu lượng. Nếu dùng subnet tin cậy, thay `<HOST_IP>/32` bằng CIDR tương ứng. Với NAT forwarding, xác minh IP nguồn thực tế mà VM thấy trước khi giới hạn. Các lệnh iptables trên không tự tồn tại qua reboot: lưu rule bằng cơ chế phù hợp distro hoặc cấu hình firewall hiện tại. Với Docker nftables backend, dùng rule forward tương ứng theo tài liệu Docker; không chạy lệnh DOCKER-USER nếu chain không tồn tại. Xem [Docker và firewall](https://docs.docker.com/engine/network/packet-filtering-firewalls/) và [DOCKER-USER](https://docs.docker.com/engine/network/firewall-iptables/).

## Chuẩn bị Git trên máy VS Code

Từ workspace JobApply, trước khi thay đổi:

```sh
git status --short --branch
git branch --show-current
git remote -v
```

Nếu chưa có remote:

```sh
git remote add origin https://github.com/nguyenkdy/JobApply.git
git remote -v
```

Nếu đã có remote, đối chiếu URL đúng repo; không tự ghi đè remote hoặc lịch sử. Khi repo GitHub đích đang trống, push branch đã chuẩn bị:

```sh
git push -u origin main
```

Nếu repo đích có lịch sử, chạy `git fetch origin`, kiểm tra quan hệ branch và thống nhất cách tích hợp trước. Không force-push, không dùng `--allow-unrelated-histories` tự động để vượt lỗi.

Các lần sửa tiếp theo:

```sh
git status --short
git diff
# Stage chính các file của thay đổi, kiểm tra không có .env/CV/dữ liệu:
git add <FILE_1> <FILE_2>
git diff --cached --stat
git commit -m "Mô tả thay đổi JobApply"
git push origin main
```

`.gitignore` loại trừ `.env`, secrets/private keys, CV PDF, database, dump/backup, virtualenv, node_modules, build và file kiểm thử sinh ra. Chỉ `.env.example` với placeholder được commit. `.gitattributes` giữ LF cho shell script Linux.

## Triển khai lần đầu — chạy trên VM

### 1. Kiểm tra công cụ

```sh
git --version
docker --version
docker compose version
docker info
curl --version
```

Dùng Docker Compose plugin v2 có `--wait` (khuyến nghị 2.20+). Nếu thiếu, cài Docker Engine và Compose plugin theo distro VM: [hướng dẫn Docker Engine chính thức](https://docs.docker.com/engine/install/), [Compose plugin](https://docs.docker.com/compose/install/linux/). Nếu lỗi permission socket, xử lý quyền user với Docker trên VM; không dùng `chmod 666 /var/run/docker.sock`. Không cần Python/Node trên VM host vì mọi runtime nằm trong image.

VM hiện tại là Ubuntu 24.04, tài khoản `myserver`. Repository có script cài từ kho APT chính thức của Docker; script dừng nếu gặp runtime/package xung đột và không xóa dữ liệu hoặc tắt firewall:

```sh
sudo sh scripts/install-docker-ubuntu.sh myserver
```

Nhập mật khẩu sudo trực tiếp trên terminal VM. Script thêm `myserver` vào group `docker` để quản trị Docker, nên cần mở phiên SSH mới sau khi cài. Không gửi mật khẩu vào chat hoặc cấp `NOPASSWD: ALL` để vượt bước xác thực này.

### 2. Clone đúng repo và branch

```sh
git clone --branch main https://github.com/nguyenkdy/JobApply.git JobApply
cd JobApply
git status --short --branch
git remote -v
```

Branch triển khai là `main`. Không clone đè lên thư mục có dữ liệu.

### 3. Tạo cấu hình riêng trên VM

```sh
cp .env.example .env
chmod 600 .env
nano .env
```

Thay toàn bộ `CHANGE_ME...` bằng secrets ngẫu nhiên. Bốn mật khẩu DB dùng chuỗi hex/chữ số, không khoảng trắng hoặc ký tự đặc biệt trong URL. `JWT_SECRET` tối thiểu 32 ký tự ngẫu nhiên. Không gửi secrets lên terminal/log hoặc commit Git. Nếu VM có Python, có thể dùng `python3 scripts/configure.py` thay bước copy/nano để tự sinh secrets vào file (script không in giá trị và không ghi đè file có sẵn), sau đó `chmod 600 .env`.

| Biến | Mục đích |
|---|---|
| POSTGRES_PASSWORD | Mật khẩu admin PostgreSQL để init/test |
| ACCOUNT_DB_PASSWORD | User account_user, chỉ database account_db |
| JOB_DB_PASSWORD | User job_user, chỉ database job_db |
| APPLICATION_DB_PASSWORD | User application_user, chỉ database application_db |
| JWT_SECRET | Khóa ký JWT chung cho ba backend trong môi trường demo tin cậy |
| TOKEN_MINUTES | Thời hạn token, mặc định 120 phút |
| APP_BIND_ADDRESS | Mặc định `0.0.0.0`, để publish web trên interface VM; có thể đặt chính IP VM để thu hẹp interface |
| APP_PORT | Cổng web trên VM, mặc định `8080` |

Browser dùng `/api/...` tương đối. API liên service dùng DNS Docker `account`, `job`, `application`. Không cần điền IP VM vào JavaScript, không cần CORS wildcard. Đăng nhập dùng Bearer token trong sessionStorage, không cookie `Secure`/redirect localhost; hỗ trợ HTTP trên IP nội bộ. Cấu hình HTTP này dành riêng cho demo local, không phải cấu hình public Internet.

### 4–5. Build → PostgreSQL → migrations → toàn bộ ứng dụng

Lệnh tự động (script không seed/reset):

```sh
sh scripts/deploy-vm.sh first
```

Hoặc thực hiện tương đương bằng tay:

```sh
docker compose config --quiet
docker compose build account job application frontend
docker compose up -d --wait postgres
docker compose run --rm --no-deps account python scripts/migrate.py account
docker compose run --rm --no-deps job python scripts/migrate.py job
docker compose run --rm --no-deps application python scripts/migrate.py application
docker compose up -d --wait
```

API entrypoint cũng chạy `upgrade head` trước Uvicorn; lặp lại an toàn. `depends_on: service_healthy` đảm bảo database/API phụ thuộc sẵn sàng. Đường tải CV Account → Application không gây vòng dependency khởi động; chỉ gọi khi có request recruiter.

### 6. Seed demo bằng lệnh riêng

```sh
docker compose --profile tools run --build --rm seed
```

Chạy lại không tạo trùng. Seed chỉ dùng API, không ghi đè mật khẩu/hồ sơ/job đã thay đổi. Seed **không** chạy trong `up` hoặc cập nhật thông thường. Tài khoản demo trong README chỉ dùng local.

### 7. Health và truy cập

```sh
docker compose ps
sh scripts/smoke-vm.sh http://<VM_IP>:8080
docker compose exec -T account python scripts/smoke-workflow.py --base-url http://frontend
```

Script endpoint kiểm tra web, health ba service, tìm job công khai và HTTP 401 trên API cần đăng nhập. Bất kỳ lỗi nào trả exit code khác 0. Script workflow đi HTTP thật qua Nginx, tạo hai tài khoản/công ty/job/CV giả, đăng/tìm/nộp, kiểm nộp trùng, tải CV, đổi trạng thái, kiểm lịch sử rồi rút hồ sơ/đóng job. Nó để lại các bản ghi `Smoke ...` để kiểm tra, không xóa dữ liệu tự động.

Cuối cùng trên máy thật mở **http://<VM_IP>:8080**, đăng nhập hai vai trò và chạy kịch bản README. Smoke chạy trong VM không thay thế kiểm tra route/firewall từ máy thật.

## Cập nhật phiên bản — chấp nhận downtime ngắn

Sau khi code đã được commit và push từ máy VS Code, SSH vào VM:

```sh
ssh <VM_USER>@<VM_IP>
cd <PATH_TO_JOBAPPLY>
git status --short --branch
git branch --show-current
git remote -v
```

**Nếu working tree có thay đổi local hoặc file chưa track, dừng.** Kiểm tra và bảo toàn những thay đổi đó trước khi pull. Không tự stash, reset, clean hoặc bỏ qua conflict. `.env` là file ignored, được giữ riêng trên VM.

Cập nhật tự động:

```sh
sh scripts/deploy-vm.sh update
sh scripts/smoke-vm.sh http://<VM_IP>:8080
```

Script kiểm tra working tree/upstream, chạy `git pull --ff-only`, build trước khi dừng bản đang chạy, dừng frontend/API, giữ PostgreSQL, chạy migration theo thứ tự, rồi `up -d --wait`. Nếu có lỗi, script dừng và trả mã khác 0; không xóa dữ liệu hoặc vượt lỗi. **Không chạy thêm `git pull` trước script nếu muốn script làm toàn bộ bước pull.**

Lệnh thủ công tương đương sau khi working tree sạch và đúng branch/remote:

```sh
git pull --ff-only origin main
docker compose config --quiet
docker compose build account job application frontend
docker compose stop frontend application job account
docker compose up -d --wait postgres
docker compose run --rm --no-deps account python scripts/migrate.py account
docker compose run --rm --no-deps job python scripts/migrate.py job
docker compose run --rm --no-deps application python scripts/migrate.py application
docker compose up -d --wait
sh scripts/smoke-vm.sh http://<VM_IP>:8080
docker compose ps
```

Build dùng cache nên có thể chạy mỗi lần; đổi dependency, Dockerfile, backend hoặc frontend cần build image mới. Thay `.env` cần recreate container; `up -d` nhận diện thay đổi cấu hình. Không đổi DB password tùy tiện trên volume đã init: init script chỉ chạy khi dữ liệu PostgreSQL trống, không tự đổi mật khẩu user đã có. Đổi JWT secret làm hết hiệu lực các token cũ.

Không tự rollback migration bằng cách checkout code cũ. Nếu migration/update lỗi, giữ downtime, đọc log và sửa tiến tới; backup trước thay đổi schema quan trọng. Kiểm tra volume tồn tại trước/sau cập nhật bằng `docker volume ls --filter label=com.docker.compose.project=jobapply`.

## Kiểm thử bổ sung trên VM

```sh
docker compose --profile test run --build --rm tests
docker compose exec -T account python scripts/smoke-workflow.py --base-url http://frontend
```

Lệnh đầu chạy pytest với PostgreSQL thật, gồm nộp đồng thời, ACL, chuyển trạng thái và migration. Runner tạo/xóa các database test có tên ngẫu nhiên, không đụng database ứng dụng. Lệnh thứ hai kiểm tra tích hợp network/container/Nginx thật.

Nếu có Node và browser trên máy thật, có thể chạy Playwright từ `frontend/` nhắm vào VM mà không chạy Docker ở đó:

```powershell
$env:E2E_BASE_URL = 'http://<VM_IP>:8080'
$env:PLAYWRIGHT_CHANNEL = 'chrome'
npm run test:e2e
```

## Chẩn đoán lỗi

```sh
docker compose ps
docker compose logs --tail=100 postgres account job application frontend
curl -f http://127.0.0.1:8080/health
sh scripts/smoke-vm.sh http://<VM_IP>:8080
```

- Localhost VM hoạt động nhưng máy thật không vào: kiểm tra IP, Bridged/NAT/forwarding, bind address, firewall/DOCKER-USER và cổng host bị chiếm.
- 502/503: kiểm tra health và log API; không seed hoặc xác nhận demo thành công khi dependency chưa sẵn sàng.
- Migration báo authentication: đối chiếu cấu hình đã dùng để tạo volume, không reset DB để vượt lỗi.
- `.env` còn placeholder/JWT quá ngắn: sửa trên VM rồi chạy lại; không dùng `docker compose config` không có `--quiet` để chia sẻ output vì có thể lộ secrets.
- CV 413: file vượt giới hạn 5 MB (gateway giới hạn request 6 MB). PDF sai MIME/cấu trúc hoặc có password trả 422.

## Dữ liệu, dừng và reset riêng

`postgres_data` và `cv_data` là named volumes. Build/recreate/`stop`/`start`/`down` bình thường giữ database và CV. Compose project name cố định `jobapply`; không thay tên project hoặc dùng `-p` khác nếu muốn tiếp tục dùng chính volumes đang có.

```sh
docker compose stop
docker compose start
# Hoặc bỏ container/network nhưng GIỮ volumes:
docker compose down
docker compose up -d --wait
```

**RESET — xóa vĩnh viễn toàn bộ database và CV:** chỉ thực hiện khi chủ động muốn bắt đầu lại, không dùng trong cập nhật thông thường.

```sh
docker compose down --volumes
sh scripts/deploy-vm.sh first
docker compose --profile tools run --build --rm seed
```

Không có script tự động reset. Không dùng reset để xử lý Git conflict, migration lỗi, đăng nhập lỗi hoặc dependency chưa healthy.
