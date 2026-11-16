# Đã xóa lô 200 CV mở rộng v5 — 16/11/2026

Theo yêu cầu người dùng, đã xóa lô 200 CV synthetic không đạt mục tiêu chia nhóm độc lập. Lô này có 200 kịch bản nhưng dùng chung một khung ghép nội dung; các split 120/40/40 và 200/0/0 không còn là đầu vào hiện hành. Không giữ lô này làm train/hồi quy.

Đã xóa:

- Assets `ml_data_assets/expanded_cv_v5` cùng nội dung, metadata và nguồn kịch bản.
- Năm run `20261116_expanded_cv_v5_01` đến `_05`, bản assets sửa lineage và thư mục báo cáo phát sinh; gồm mọi bản snapshot CV, dataset kết hợp, cặp ứng viên và split của lô này.
- `ml_data/expanded.py`, `ml_data/role_compatibility.py` (chỉ được công cụ vừa gỡ sử dụng), script tác giả hóa/sinh báo cáo, `tests/ml/test_expanded.py`, hai lệnh CLI chuẩn bị/kiểm tra preview và cache riêng.
- Báo cáo preview cùng JSON kết quả của lô bị loại. Đã gỡ các file lô này đang được stage khỏi Git index.

Tám thư mục dữ liệu đã xóa chứa 536 file, tổng 189.517.164 byte; số này chưa tính code/test/báo cáo rời và cache. [Receipt xóa](reports/20261116-retired-200-cv-cleanup.json) chỉ giữ đường dẫn, số lượng và checksum để xác nhận phạm vi; không chứa nội dung CV hoặc dữ liệu cá nhân.

Giữ nguyên ba CSV upstream, catalog 788 JD, metadata JD v4, dữ liệu pilot, lô CV trước đó dùng trong Bước 4 và các kết quả/model lịch sử. Chưa train hoặc tạo nhãn từ lô 200 CV nên không có model cần thu hồi. Các kế hoạch số lượng CV trong báo cáo metadata cũ được đánh dấu là lịch sử; chưa có lô mở rộng thay thế.

Không yêu cầu vòng người review. Vấn đề cần giải quyết trước lần tạo CV kế tiếp là nguồn/kịch bản và khung sinh độc lập thực sự, không tăng số lượng bằng thay tiêu đề hoặc bố cục rồi chia ngẫu nhiên. Kiểm tra lineage phải diễn ra từ thiết kế trước khi sinh hàng loạt.

Kết quả kiểm thử sau xóa được ghi tại [TESTING.md](../../TESTING.md). Sau đợt xóa đã tạo [lô tiếp nhận nhỏ v6](authored_cv_intake.md) bằng văn bản mới viết riêng; không khôi phục generator/nội dung v5. Câu “chưa có lô mở rộng thay thế” phía trên mô tả thời điểm dọn dẹp.
