# Định nghĩa nhãn cho đề xuất việc làm — rà soát 17/11/2026

**Cập nhật 17/11/2026 — Đã triển khai trong `v4` và mở rộng trong `v5`:** Hợp đồng nhãn dưới đây đã được hiện thực hóa bằng luật đóng có bằng chứng trong [`task-evidence-proxy-v4`](task_matching_v4.md) (`107` nhãn 0, `325` nhãn 1, `0` nhãn 2) và mở rộng độ phủ ngữ pháp trong [`task-evidence-proxy-v5`](task_matching_v5.md) (`290` nhãn 0, `4.227` nhãn 1, `3` nhãn 2, `120/120` CV và `489/788` JD có bằng chứng nhiệm vụ; kiểm chứng bất biến đổi tên chức danh trên cả 48.284 cặp). Các nhãn tạo ra vẫn là `automatic_rule_proxy` ở chế độ `development`, không phải gold và không chứng nhận năng lực hay quyết định tuyển dụng.

*(Ghi chú tại thời điểm soạn thảo trước v4:)* Nhãn trước đó do `expanded-technical-proxy-v3` tạo. Tài liệu này là hợp đồng cho vòng đối chiếu theo nhiệm vụ, không phải gold, không yêu cầu vòng hai reviewer, không chứng nhận năng lực hoặc quyết định tuyển dụng.

## Câu hỏi mà nhãn phải trả lời

“Dựa trên bằng chứng chuyên môn ghi trong CV và yêu cầu JD này, công việc có đáng được ưu tiên đề xuất cho người dùng không?”

Không đánh đồng câu hỏi đó với “ứng viên chắc chắn đáp ứng mọi tiêu chí tuyển dụng”. Bằng chứng giới hạn ở hồ sơ được cung cấp; không khẳng định người đó không có kỹ năng chỉ vì CV không nhắc tới. Phạm vi benchmark kỹ thuật phải ghi rõ: nhiệm vụ, kỹ năng/stack và kinh nghiệm. Học vấn, ngoại ngữ hoặc điều kiện khác chưa được đánh giá phải được khai báo, không gọi nhãn 2 là đáp ứng toàn bộ JD.

## Những khác biệt đã xác minh trong quy tắc hiện tại

| Điểm | Luật lịch sử 14/11 | Luật v3 đang chạy | Định nghĩa đề xuất |
|---|---|---|---|
| Hai tên nghề khác nhau | Có thể gán 0 trực tiếp | Chưa kết luận nếu thiếu nhiệm vụ chung | So nhiệm vụ cốt lõi có bằng chứng; không dùng tên nghề làm kết luận |
| Nhãn 1 | Cùng nghề, kể cả không giao công nghệ | Công nghệ chung và cùng nghề hoặc nhiệm vụ chung | Cần liên quan chuyên môn có ý nghĩa; một từ khóa chung chưa đủ |
| Nhãn 2 | Các ngưỡng đã trích xuất được đáp ứng | Bắt buộc cùng nghề cụ thể, có điều kiện công nghệ **và** thời lượng đã đọc, không unresolved | Không bắt mọi JD phải có yêu cầu số năm; chỉ đối chiếu điều kiện thực sự tồn tại, sau kiểm đầy đủ phần yêu cầu thuộc phạm vi |
| Thiếu dữ liệu | Quy tắc phụ thuộc phiên bản | Giữ trống hoặc nhãn 1 theo bằng chứng khác | Phân biệt nguồn thiếu, parser chưa hiểu, điều kiện không áp dụng và bằng chứng trái yêu cầu |

V3 có thể không tạo được nhãn 2 cho JD không đòi số năm, dù CV phù hợp: đó là tiền đề của luật, không phải lỗi văn bản hay bằng chứng ứng viên không phù hợp. Việc parser không trích xuất được thời lượng **không chứng minh** JD không có yêu cầu thời lượng.

## Định nghĩa đề xuất, chưa dùng chấm lại

| Nhãn/trạng thái | Điều kiện |
|---|---|
| **0 — ít ưu tiên do có căn cứ không đáp ứng** | Có mâu thuẫn rõ với điều kiện chuyên môn bắt buộc, áp dụng được, ví dụ thiếu thời lượng đã xác nhận trong cùng scope. Có thể mở thêm nhánh nhiệm vụ cốt lõi không tương thích **sau khi** có mô tả nhiệm vụ hai phía đủ rõ và quy tắc tương thích được kiểm chứng; nhánh này chưa được triển khai. Không dùng title mismatch hoặc thiếu mention làm nhãn 0. |
| **1 — liên quan một phần** | Có bằng chứng nhiệm vụ/kỹ năng cốt lõi liên quan, chưa đủ hỗ trợ mức 2 và không có mâu thuẫn bắt buộc rõ ràng. Có thể còn thiếu bằng chứng đáp ứng một yêu cầu. Lưu điều kiện chưa rõ thay vì che nó trong điểm số. |
| **2 — ưu tiên cao trong phạm vi kỹ thuật đã khai báo** | Nhiệm vụ cốt lõi tương thích; có bằng chứng kỹ năng cần thiết; mọi điều kiện bắt buộc **thuộc phạm vi** đã được xác định và đối chiếu đều được hỗ trợ. Không còn điều kiện quan trọng chưa đọc/không rõ. Yêu cầu không có trong JD không tự được thêm vào. Không bắt title phải giống chuỗi. |
| **insufficient_evidence — trống** | Không đủ xác định quan hệ công việc hoặc nội dung quan trọng chưa hiểu. Không thể phân biệt 0/1/2 một cách có căn cứ. |
| **out_of_scope — trống** | JD ngoài phạm vi đánh giá đã khai báo; giữ trong kho với lý do, không biến thành negative để tăng lớp 0. |
| **unprocessed — trống** | Chưa chạy quy trình. Phân biệt với đã chạy nhưng chưa kết luận. |

Không áp dụng nhánh “không tương thích nhiệm vụ” chỉ để điền 37.120 cặp trống. Trước khi triển khai phải định nghĩa nhiệm vụ, chiều tương thích và trường hợp chuyển nghề; kiểm bằng các tình huống đối chứng độc lập với điểm model.

## Trạng thái từng điều kiện phải lưu

- `supported`: có bằng chứng CV đáp ứng điều kiện JD.
- `contradicted`: có bằng chứng rõ không đạt điều kiện bắt buộc; cả phạm vi và loại kinh nghiệm so được.
- `not_demonstrated`: chưa thấy bằng chứng trong CV đã đọc đầy đủ; không có nghĩa ứng viên không có kỹ năng.
- `source_unknown`: văn bản để trống hoặc nói rõ không đủ thông tin.
- `extraction_unresolved`: có nội dung/cấu trúc liên quan nhưng công cụ chưa phân giải được.
- `not_applicable`: điều kiện không áp dụng hoặc không được JD yêu cầu, chỉ sau khi kiểm đủ phạm vi; không suy từ danh sách parser rỗng.

Mỗi điều kiện cần ID hồ sơ/hash, trường nguồn, câu bằng chứng/offset, bắt buộc hay ưu tiên, cây AND/OR, scope, loại kinh nghiệm, cận và phương pháp/phiên bản trích xuất. `not_demonstrated` cần ghi phạm vi văn bản đã kiểm; `not_applicable` cần căn cứ kiểm đủ JD. Thiếu công nghệ không đổi thành 0 tháng; kinh nghiệm dự án/thực tập không tự đổi thành employment.

## Các tình huống phải kiểm trước khi áp dụng

| Tình huống | Kết quả mong đợi theo hợp đồng đề xuất |
|---|---|
| CV ghi Python 12 tháng làm việc; JD bắt buộc Python từ 36 tháng | 0 nếu điều kiện áp dụng được và bằng chứng cùng scope |
| CV có 36 tháng tổng kinh nghiệm, JD cần 24 tháng Python | Thời lượng Python unknown; không tự đạt hoặc không đạt. Có thể 1 nếu bằng chứng nhiệm vụ phù hợp, nếu không thì trống |
| CV không nhắc Docker, JD bắt buộc Docker | `not_demonstrated`, không tự 0; mức cặp phụ thuộc bằng chứng còn lại |
| CV chỉ Python để huấn luyện ảnh, JD Python để phát triển API | Từ khóa chung chưa đủ nhãn 1; chưa có quy tắc nhiệm vụ thì để trống |
| Backend Developer và API Engineer, đều có nhiệm vụ API phù hợp | Không bị loại vì khác title; có thể 2 khi mọi điều kiện kỹ thuật đã kiểm đều đạt |
| JD không yêu cầu thời lượng, nhiệm vụ/kỹ năng đã được kiểm đủ | Không chặn 2 chỉ vì không có số tháng |
| JD còn mệnh đề bắt buộc chưa hiểu | Không được 2 |
| JD ghi Python hoặc Java; CV chứng minh Java | Đạt nhánh OR; không bắt phải có Python |
| CV chưa dùng Kubernetes; JD chỉ ưu tiên Kubernetes | Không gán 0 từ ưu tiên |
| CV chỉ ghi thực tập; JD cần kinh nghiệm làm việc chính thức | Không tự quy đổi; chưa đủ bằng chứng so thời lượng thì unknown |

## Quyết định tiếp theo

Hoàn thành kiểm kê hồ sơ và chọn bộ tình huống development để so cách trích xuất. Chưa quyết định dùng LLM thay regex; chưa chọn model/nhà cung cấp. Thử nghiệm sau phải kiểm evidence, scope và logic điều kiện, đo độ đúng trên mệnh đề thay vì chỉ đếm ô được điền. Không dùng chính parser hiện tại làm chân lý để chứng minh parser mới đúng.

Nhãn tiếp theo vẫn là proxy tự động. Nếu feature và nhãn cùng sinh từ metadata/quy tắc, model có thể chỉ học mô phỏng bộ luật; khi thí nghiệm phải giữ baseline luật và phân tích điều này. Toàn bộ 120 CV hiện tại tiếp tục development; chưa có final test độc lập. Data Analyst vẫn thuộc mục tiêu nghiên cứu, cần xử lý nguồn JD đủ điều kiện riêng.
