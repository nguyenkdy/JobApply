# Nhãn tự động — quy tắc và giới hạn

Ngày 14/11/2026. Dùng `automatic-proxy-labeler-v3-scoped-coverage`; không yêu cầu người chấm, calibration hoặc vòng hai reviewer. Nhãn tự động là mục tiêu thí nghiệm nội bộ, không phải gold hoặc bằng chứng về mức phù hợp thật. Bộ luật được cố định trước khi sinh nhãn lô CV mới.

- `0`: hai nghề chính đều được xác định và khác nhau theo quy tắc hiện tại. Từ khóa chung không đủ làm hai nghề tương đương.
- `1`: cùng nghề và hai bên có metadata kỹ năng, nhưng chưa đủ căn cứ để đạt mức 2. Bao gồm hai tập công nghệ đã biết không giao nhau (chỉ tương thích ở mức nghề), thiếu stack chung, thời lượng chưa rõ/chưa đủ hoặc không thể so sánh thực tập/dự án với kinh nghiệm nghề.
- `2`: cùng nghề, có stack chung và **mọi ngưỡng kinh nghiệm đã trích xuất** đều có scope tương đương được CV chứng minh và đáp ứng cận tương ứng. Đây là độ phù hợp **theo quy tắc proxy**, không khẳng định đáp ứng mọi yêu cầu bắt buộc trong JD.
- `insufficient_evidence`: nghề mơ hồ/thiếu, hoặc cùng nghề nhưng một phía thiếu hẳn metadata kỹ năng. Khác với hai tập kỹ năng đã biết nhưng không giao nhau. Ô `relevance_0_1_2` phải trống; không biến thành 0.
- `unlabeled`: chưa xử lý, nhãn vẫn trống.

Không dùng `max()` của mọi scope, không suy số tháng công nghệ từ tổng năm, không quy thời gian thực tập/dự án thành làm việc chính thức, không dùng yêu cầu tùy chọn/giới hạn tối đa làm mức tối thiểu. Cận `>` khác `>=`; không cho phép thiếu 3 tháng nhưng giải thích là đã đủ. Unknown giữ `{}`. Quy tắc còn có giới hạn: so nghề/kỹ năng chưa hiểu trọn nhiệm vụ, điều kiện AND/OR hay mọi yêu cầu chuyên môn.

Thời lượng nghề/phát triển phần mềm chỉ so sánh nếu CV có câu nói rõ đúng scope đó; thời gian Python/Java/React cần evidence riêng. JD giữ câu yêu cầu kèm offset và toán tử AND/OR, ưu tiên, logic trộn/chưa phân giải. Receipt này phục vụ kiểm tra, chưa phải bộ giải ngữ nghĩa toàn bộ yêu cầu; danh sách mơ hồ không được tự coi là tất cả bắt buộc.

`validate-labels` kiểm tra ID trùng, phiên bản/hash văn bản, schema và evidence nguyên văn. `complete=true` chỉ khi **mọi hàng có nhãn số**; không phải chỉ vì đã xử lý hết hàng. Hợp lệ schema không chứng minh nhãn đúng ngữ nghĩa. Evidence đầy đủ lấy từ văn bản chuyên môn nguồn; không tự bịa trích dẫn.

`label-pairs` yêu cầu output mới, giữ `source_pairs.csv`, manifest nguồn, phiên bản bộ luật, `label_origin=automatic_rule_proxy`, `human_verified=false`. Không ghi đè nhãn/pilot/run cũ. 30 cặp calibration lịch sử còn trong snapshot nhưng công cụ tạo chúng đã bỏ.

```powershell
Set-Location D:\JobApply
$labelOut = '.\ml_data_runs\labels_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
python -m ml_data label-pairs --dataset .\ml_data_runs\DATASET_RUN\dataset --pairs .\ml_data_runs\PAIR_RUN --jd-extraction .\ml_data_runs\EXTRACTION_RUN --output $labelOut
if ($LASTEXITCODE -ne 0) { throw 'Automatic labeling failed' }
python -m ml_data validate-labels --pairs .\ml_data_runs\PAIR_RUN\pairs.csv --labels "$labelOut\pairs.csv"
```

Các tên `DATASET_RUN`, `PAIR_RUN`, `EXTRACTION_RUN` phải thay bằng artifact thật đã xác minh. Dataset và văn bản từng cặp phải cùng phiên bản. Kết quả sửa nhãn của split cũ lỗi chỉ là chẩn đoán, không tự trở thành tập huấn luyện hợp lệ. Lô mới dùng 60 CV / 12 họ khác, đã đủ 3.000 nhãn số; xem [bàn giao trước Bước 4](pretraining_handoff.md). Mức độ đầy đủ này không đo độ đúng của nhãn; feature/nhãn cùng dựa trên metadata cần baseline luật và ablation khi thí nghiệm sau này.
