# Mốc 1 — Công cụ calibration và đối chiếu

**Trạng thái: mới hoàn thành phần công cụ.** Rubric chưa được chuyên gia duyệt; hai bộ phiếu đều chưa có câu trả lời. Chưa có nhãn được xác minh, chưa tạo final-test labels, chưa train/chọn model bằng rubric này.

## Tài liệu và bộ phiếu sẵn dùng

- [Rubric dự thảo v0.1](annotation_guidelines.md): gửi người có chuyên môn đọc và phản hồi trước khi chấm calibration.
- [Phiếu reviewer A](calibration/20261112_v1/reviewer_A/review.csv) và [hướng dẫn A](calibration/20261112_v1/reviewer_A/annotation_guidelines.md).
- [Phiếu reviewer B](calibration/20261112_v1/reviewer_B/review.csv) và [hướng dẫn B](calibration/20261112_v1/reviewer_B/annotation_guidelines.md).
- Chỉ điều phối đọc [manifest chọn mẫu](calibration/20261112_v1/coordinator/batch_manifest.json) và [hash phiếu gốc](calibration/20261112_v1/coordinator/packet_hashes.json). Không giao thư mục coordinator hay repo chứa nhãn AI cho reviewer trong lúc chấm độc lập.

Lô 24 cặp từ pilot development có 4 cặp/CV, chọn bằng seed `20261112`; thứ tự reviewer dùng seed `20261113` và `20261114`. Sáu cặp cùng nhóm nghề/có stack chung, sáu cặp có skill chung khác nhóm nghề, sáu cặp để xem xét ngưỡng kinh nghiệm, ba cặp có thông tin chưa đối chiếu được và ba cặp có yêu cầu ưu tiên. Các nhóm là **lý do lấy mẫu**, không phải kết luận relevance và không hiện trong phiếu.

Tool không đọc score/rank, nhãn hay rationale AI để chọn hoặc tạo phiếu. Nó dùng văn bản chuyên môn, nhóm nghề chọn mẫu và chú thích kinh nghiệm pilot để đa dạng hóa tình huống. Các metadata này vẫn có giới hạn và cần người có chuyên môn xem lại; calibration không phải mẫu đánh giá đại diện thị trường.

Mỗi phiếu chỉ có ID cặp ẩn danh, slot người nhận, phiên bản rubric, hash và toàn bộ văn bản chuyên môn CV/JD, cùng các cột trả lời trống. Không có ID nguồn để tiện dò nhãn. Hash là SHA256 UTF-8 của text sau khi đọc CSV với universal newlines. Văn bản chưa được chuyên gia xác nhận đầy đủ/chuẩn hóa hoàn hảo; chính những chỗ không rõ phải được ghi `needs_review` hoặc `insufficient_evidence`.

Việc đặt file A/B ở thư mục riêng là phân phối tài liệu, **không phải phân quyền truy cập**. Điều phối phải chỉ gửi từng gói riêng cho từng người. Reviewer đã xem nhãn AI hoặc câu trả lời người kia cần báo hạn chế trước; công cụ không thể xác thực độc lập bằng mã người dùng.

## PowerShell — chuẩn bị và kiểm tra

Các lệnh chạy từ `D:\JobApply`. `annotation.py` chỉ cần thư viện chuẩn Python; không cần môi trường ML, mạng, Docker hay database. Giữ bộ phiếu gốc nguyên vẹn; dùng bản sao để điền. `annotation_work/` được Git ignore cho bản trả lời và báo cáo làm việc, không tự gửi/commit thông tin reviewer.

```powershell
Set-Location D:\JobApply
$batch = '.\docs\ml\calibration\20261112_v1'
$workId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$work = ".\annotation_work\$workId"
New-Item -ItemType Directory -Path $work -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath "$batch\reviewer_A" -Destination "$work\reviewer_A" -Recurse
Copy-Item -LiteralPath "$batch\reviewer_B" -Destination "$work\reviewer_B" -Recurse
```

Điều phối giao riêng thư mục A cho người A, thư mục B cho người B. Mỗi người tự ghi `annotator_id`, `human_independent`, trạng thái, nhãn nếu đủ căn cứ, trích đoạn CV/JD, rationale và thời gian thực tế theo guideline. Không tự điền các trường này bằng script. Không sửa text/hash/ID hoặc xóa dòng chưa chấm.

Kiểm tra từng bản trả lời sau khi nhận:

```powershell
python .\jobapply_pilot_v1\annotation.py validate --batch-dir $batch --reviewer A --input "$work\reviewer_A\review.csv"
if ($LASTEXITCODE -ne 0) { throw 'Reviewer A file has validation errors.' }
python .\jobapply_pilot_v1\annotation.py validate --batch-dir $batch --reviewer B --input "$work\reviewer_B\review.csv"
if ($LASTEXITCODE -ne 0) { throw 'Reviewer B file has validation errors.' }
```

Exit 0 nghĩa schema/nội dung đáp ứng quy tắc công cụ, không nghĩa đã chấm đủ hoặc nhãn đúng. Luôn đọc `counts` và `eligible_completed`. Phiếu chưa bắt đầu hợp lệ và có eligible=0. Khi điền dở mà chưa có trạng thái, công cụ báo lỗi thay vì âm thầm coi là nhãn 0.

Đối chiếu và tạo phiếu phân xử trống:

```powershell
$comparison = "$work\comparison"
python .\jobapply_pilot_v1\annotation.py compare --batch-dir $batch --a "$work\reviewer_A\review.csv" --b "$work\reviewer_B\review.csv" --output $comparison
if ($LASTEXITCODE -ne 0) { throw 'Comparison failed; inspect inputs.' }
Copy-Item -LiteralPath "$comparison\adjudication.csv" -Destination "$work\adjudication.returned.csv"
```

`comparison/` là snapshot bất biến: giữ byte hai CSV gốc, report, queue và hash. Không lưu đè; mỗi lần sửa reviewer CSV tạo thư mục comparison mới. `adjudication.csv` giữ nguyên hai đánh giá/evidence/rationale, bổ sung các trường kết luận cuối trống. Cặp chưa đủ hai đánh giá có `queue_reason=awaiting_reviews`; cần hoàn thành bước độc lập trước khi phân xử. Cặp chưa rõ hoặc có origin AI được tách khỏi các bất đồng nhãn số.

Người thứ ba có chuyên môn điền bản `adjudication.returned.csv`: `adjudicator_id` khác hai reviewer, `annotation_origin=human_adjudicated`, `final_status`, `final_label` hoặc để trống khi chưa rõ, trích đoạn hai phía, `adjudication_rationale`, `adjudicated_at`. Không sửa các cột A/B. Công cụ không lấy trung bình hay tự quyết định nhãn cuối.

```powershell
python .\jobapply_pilot_v1\annotation.py validate-adjudication --comparison-dir $comparison --input "$work\adjudication.returned.csv"
```

Các cặp đồng thuận không tự trở thành final/gold; không có bước tự xuất tập train từ phiếu này. Specialist và điều phối còn phải duyệt rubric/provenance, xử lý bất đồng có hệ thống và quyết định phiên bản dữ liệu. Nếu sửa rubric hoặc text, tạo batch mới và chấm lại phần chịu ảnh hưởng, không đổi tên version của phiếu cũ.

## Tái tạo lô calibration

Run nguồn đầy đủ được lưu local ngoài Git; receipt chỉ có hash không thay thế các artifact. Dùng run hoàn tất có đủ snapshot input. Mọi output phải là đường dẫn chưa tồn tại:

```powershell
$run = '.\jobapply_pilot_v1\results\reruns\20261112_baseline_03'
python .\jobapply_pilot_v1\annotation.py prepare --run-dir $run --output "$work\calibration_recreated" --seed 20261112
```

`prepare` lưu seed, version, nguồn/hash, số ứng viên đủ điều kiện lấy mẫu, lý do chọn và hash bộ phiếu. Mọi quyết định relevance/evidence/rationale vẫn trống. Bản hiện hành dành cho thiết kế calibration sáu CV pilot; không phải công cụ tự mở rộng dataset hàng loạt.

## Cách đọc báo cáo

Chỉ cặp cả hai `completed` và `human_independent` mới vào thống kê nhãn số; hai slot không được dùng cùng annotator ID. Nhãn AI vẫn được nhận diện bằng `annotation_origin=ai_draft`, được đếm riêng và bị loại khỏi thống kê độc lập. Phiếu phân xử có schema riêng, không được đưa ngược vào vai trò reviewer độc lập.

- `reviewers`: số completed, chưa chấm, needs_review, insufficient_evidence và origin theo từng người.
- `agreement.eligible_pairs`: mẫu số thực tế; `exact_agreement` là tỷ lệ nhãn bằng nhau trên mẫu đó.
- `confusion_matrix`: hàng A/cột B theo nhãn `[0,1,2]`.
- Weighted Cohen’s kappa dùng trọng số bất đồng quadratic `((a-b)/2)^2`, `kappa = 1 - D_observed / D_expected`. Nếu không có cặp đủ điều kiện hoặc `D_expected=0`, trả `null` và lý do; không ép thành 0 hay 1.
- `queue_counts`: số bất đồng nhãn số, cặp chờ đánh giá, cặp chưa rõ/không độc lập. Khóa không xuất hiện có số lượng 0. `status_disagreements` báo riêng khác trạng thái.

Không có ngưỡng tự chứng nhận gold. Evidence validator chỉ kiểm một trích đoạn có thật ở mỗi phía, không xác minh nội dung lý do đúng hoặc người chấm có chuyên môn. Cần xem ma trận, nhóm lỗi, số cặp bị loại và thảo luận rubric.

## Kết quả hiện tại và kiểm thử

[Báo cáo từ hai phiếu trống](reports/20261112-calibration-unreviewed/report.json) ghi 24 chưa chấm ở mỗi slot, eligible=0, exact agreement/kappa=null (`no_eligible_pairs`); 24 dòng queue đều chờ đánh giá, không có final label. Đây là kiểm tra công cụ trên trạng thái ban đầu, không phải kết quả đánh giá của người.

Bộ kiểm thử dùng nhãn/identities giả **chỉ trong fixture test tạm `.test-data/`**, có đánh dấu `TEST ONLY`, được dọn sau test. Không điền nhãn vào phiếu thật. Chạy:

```powershell
$mlPython = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $mlPython -m unittest discover -s tests/ml -v
```

Tổng 28 test đạt: 11 regression baseline, 10 annotation, 7 demo/run. Bao phủ chọn đúng run/model/catalogue; artifact thiếu/sửa, provenance/feature order/preprocessing/môi trường; CV mới/unknown; blinding/tái tạo; schema/ID/text/evidence/status; dữ liệu trống; AI không vào agreement; cùng reviewer; kappa tính tay/không xác định; giữ hai đánh giá và yêu cầu người thứ ba khi phân xử. Test đơn vị không tải encoder từ mạng.
