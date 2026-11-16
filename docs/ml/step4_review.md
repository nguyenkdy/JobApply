# Xem và đối chiếu kết quả Bước 4

Trang offline đã tạo: `ml_data_runs/20261114_step4_review_v2/index.html`. Đây là trình xem kết quả test đã lưu, không huấn luyện hoặc tính lại điểm.

```powershell
Set-Location D:\JobApply
Start-Process '.\ml_data_runs\20261114_step4_review_v2\index.html'
```

1. Xem bảng so sánh các phương pháp ở đầu trang.
2. Chọn một trong 15 CV test, rồi chọn phương pháp. Mặc định là LR metadata C=0,1 được chọn trên validation.
3. Mở “Đọc toàn bộ CV giả lập”, đối chiếu với từng JD trong Top 5. Mỗi tin có điểm, nhãn, skill/stack chung và ngưỡng kinh nghiệm đã trích xuất.
4. Mở nội dung JD và lý do nhãn để kiểm tra cơ sở của dữ liệu. Lý do nhãn đến từ bộ luật, không phải giải thích nhân quả của model.
5. Bật “Xem cả 50 JD” để xem những tin bị xếp ngoài Top 5; đổi sang E5/BM25 để đối chiếu thứ tự.

Điểm NDCG bằng 1 là xếp hạng lý tưởng theo nhãn proxy hiện có, không phải chất lượng tuyển dụng 100%. Recall nhãn 2 chỉ xác định cho 6/15 CV test; 9 CV không có JD nhãn 2. Các điểm BM25/E5/LR có thang khác nhau, không so trực tiếp giá trị điểm giữa phương pháp.

[Báo cáo và giới hạn đầy đủ](step4_results.md), [bảng số liệu CSV](reports/20261114-step4-comparison.csv). Trang chứa CV synthetic và JD từ run local, không có kết nối ngoài và không sửa ứng dụng web. File đầy đủ tiếp tục nằm trong thư mục Git ignore.

Kiểm tra ngày 16/11/2026: 105 tổ hợp CV/phương pháp hiển thị đủ Top 5, chuyển toàn catalog hiển thị 50 JD, Chrome headless không báo lỗi JavaScript; đã xem ảnh render. Generator đối chiếu tất cả Top 5 với metric đã lưu và 5.250 dòng điểm với nhãn nguồn.

Tái tạo trang vào thư mục mới:

```powershell
$reviewOut = '.\ml_data_runs\step4_review_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe .\scripts\view-step4-results.py --run .\ml_data_runs\20261114_step4_v1_01 --output $reviewOut
if ($LASTEXITCODE -ne 0) { throw 'Result viewer generation failed' }
Start-Process (Join-Path $reviewOut 'index.html')
```
