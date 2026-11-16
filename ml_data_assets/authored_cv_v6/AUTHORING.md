# Quy trình tác giả hóa v6

Lô nhỏ 30 hồ sơ, không thay thế mục tiêu mở rộng dữ liệu bằng tuyên bố đủ chất lượng. Đọc kiểm toán lô v5 trước khi viết; không khôi phục generator, assets hoặc nội dung của lô đã xóa.

1. Xác định ba ngân hàng kịch bản nguồn trước khi viết: nghiên cứu/phòng thí nghiệm, sản xuất sáng tạo, dịch vụ công ích. Mỗi ngân hàng có mười nghề. Không lấy JD cụ thể, ranking hoặc nhãn mục tiêu làm đầu vào.
2. Viết toàn bộ văn bản mỗi hồ sơ riêng trong `profiles.json`. Không có câu mẫu dùng chung để điền task/tools/check/limit/duration; không có renderer xây CV từ các ô nội dung. Code chỉ vận chuyển văn bản nguyên vẹn và kiểm câu bằng chứng.
3. Ngân hàng nguồn là đơn vị gom nhóm bảo thủ. Trường `template_group` của schema được dùng để giữ cả ngân hàng cùng partition, không có nghĩa mỗi ngân hàng chứng minh một tác giả hay tập ứng viên độc lập. `source_group` giữ đúng kịch bản nguồn cụ thể. Cùng tác giả AI/cohort được khai báo ở mọi hồ sơ.
4. Metadata là khẳng định của tác giả synthetic: chỉ chọn kỹ năng được nói là đã dùng, không chọn kỹ năng được phủ định. Scope thời lượng phải nằm trong câu khai báo; thời gian thực tập/dự án không đổi thành kinh nghiệm nghề nghiệp. Unknown là `{}`.
5. Dùng fixture riêng để viết kiểm thử. Không dùng CV holdout chỉnh feature/rubric. Các kiểm tra tiếp nhận (schema, evidence, hash, provenance, trùng) không phải tối ưu mô hình. Nếu dùng một hồ sơ để sửa phương pháp matching về sau, phải chuyển cả nhóm liên quan sang development.
6. Không có nguồn hoặc template cha từ lô v5. Vì nội dung v5 đã bị xóa theo yêu cầu, không thể tuyên bố đã so trùng nguyên văn với lô đó; nguồn gốc mới là khai báo tác giả, kiểm trùng thực tế chỉ áp dụng cho các lô còn được giữ.

Không dùng số nhóm hoặc độ tương đồng từ vựng để chứng nhận độc lập về ngữ nghĩa. Khác ngân hàng nguồn cũng tạo khác biệt miền nội dung; phải báo điều này khi đọc kết quả trên CV mới. Data Analyst vẫn cần JD hợp lệ trước khi thêm positive benchmark, không bị đổi tên thành Data Engineer.
