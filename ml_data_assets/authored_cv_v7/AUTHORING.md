# CV v7 — mở rộng ngân hàng kịch bản

90 hồ sơ synthetic được viết riêng thành văn bản đầy đủ, 10 nghề trong mỗi ngân hàng: commerce, transport, manufacturing, energy, hospitality, education, sports, agriculture, nonprofit. Các file JSON theo ngân hàng là bản tác giả; `profiles.json` chỉ nối danh sách bản ghi, không sinh hay lắp câu. Không có JD đích, ranking, nhãn mong muốn hoặc văn bản v5 làm đầu vào viết hồ sơ. Không có danh tính thật.

Giữ nguyên 30 CV v6 bằng snapshot và namespace cũ; không đổi tên ngân hàng, nguồn, văn bản hoặc partition của chúng. Tổng lô ghép dự kiến 120 CV / 12 ngân hàng. Không gọi 12 ngân hàng là 12 tác giả độc lập: tất cả vẫn cùng AI tác giả/cohort, nhiều cách diễn đạt và giới hạn có thể giống nhau. Ngân hàng là đơn vị giữ nhóm bảo thủ, chưa chứng minh độc lập ngữ nghĩa hay đa dạng ứng viên thật. Nội dung là các tình huống công việc ngắn, chưa đại diện CV dài nhiều trang.

Các hồ sơ mới có cùng schema và bố cục thông tin để nhập dữ liệu; không có mẫu câu được điền bằng chương trình. `source_group` giữ kịch bản cụ thể; `template_group` giữ cả ngân hàng; lineage giữ generation_version, scenario_id, shared_author, variant_history và ancestor ngân hàng. Nếu về sau tạo biến thể, phải giữ parent/ancestor cũ.

Kỹ năng là khẳng định synthetic có câu bằng chứng; chỉ liệt kê công nghệ đã dùng, không lấy phần phủ định làm kỹ năng. Tháng nghề nghiệp không suy thành tháng công nghệ, thực tập/dự án có scope riêng. Thiếu thời gian là `{}`, không phải 0. Các hồ sơ dùng sửa matching/parser về sau phải chuyển cả nhóm liên quan sang development; việc kiểm schema/lineage hiện tại không phải chọn model.

Seed cố định 20261116, giữ partition v6, chỉ phân bổ ngân hàng mới; không thử seed hoặc xem ranking để làm đẹp split. JD dùng chung là toàn bộ 788 record của metadata v4, vẫn giữ exposure phát triển parser. Data Analyst vẫn trong mục tiêu nghiên cứu, cần bổ sung JD hợp lệ trước khi có nhóm CV benchmark tương ứng.

Lô v5 đã xóa không được phục hồi. Kiểm so trùng chỉ áp dụng với dữ liệu còn tồn tại, không tuyên bố đã đối chiếu được nguyên văn v5. Không có nhãn gold hoặc người đánh giá độc lập.
