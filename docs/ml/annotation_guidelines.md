# Hướng dẫn calibration CV–JD

**Phiên bản: `jobapply-relevance-draft-v0.1`. Rubric dự thảo, chờ người có chuyên môn duyệt.** Chưa có người duyệt được ghi nhận. Phiếu sử dụng dữ liệu development/pilot, không phải final test. Chấm calibration là để phát hiện điểm chưa rõ của rubric; không tự tạo nhãn gold.

## Câu hỏi duy nhất cần đánh giá

“Dựa trên năng lực được ghi trong CV, JD này có đáng được đề xuất để ứng viên xem và cân nhắc ứng tuyển không?”

Đánh giá mức liên quan chuyên môn và yêu cầu công việc. Không đánh giá khả năng được tuyển, tính cách, ngoại hình, tên, tuổi, giới tính, địa chỉ hoặc danh tiếng trường/công ty. Không suy năng lực từ thông tin không được ghi. Một từ khóa chung hoặc tên vị trí gần nhau chưa đủ kết luận.

## Cách đọc một cặp

1. Đọc toàn bộ phần chuyên môn của CV và JD trước khi chọn nhãn. Ghi nhiệm vụ thực tế: xây API, phân tích kinh doanh, kiểm thử, vận hành hạ tầng… Tên nghề chỉ là gợi ý để đọc, không phải quy tắc chấm.
2. Xác định kỹ năng cốt lõi phục vụ nhiệm vụ. Phân biệt “đã dùng trong công việc/dự án”, “đang học”, “biết tên” và “chưa có kinh nghiệm”. Java không phải JavaScript; React không tự chứng minh kinh nghiệm React Native.
3. Tách điều kiện bắt buộc và ưu tiên theo câu chữ/đề mục. “Must/required/tối thiểu” là căn cứ mạnh hơn “preferred/nice to have/là lợi thế”. Nếu đề mục và nội dung mâu thuẫn, ghi `needs_review`; không tự đổi điều kiện thành ưu tiên để cho điểm cao. Nếu JD không phân biệt rõ, nêu cách đọc và chỗ cần phân xử.
4. Đối chiếu kinh nghiệm trong đúng phạm vi: tổng kinh nghiệm phần mềm, Python backend, DevOps, AWS… là các phạm vi khác nhau. Liệt kê AWS trong skills không chứng minh toàn bộ 24 tháng làm việc là 24 tháng AWS. Không suy số năm từ tuổi, năm tốt nghiệp hay tên seniority.
5. Xác định khoảng thiếu có bằng chứng và phần chưa biết. Không ghi trong CV không đồng nghĩa không có kỹ năng. Nếu thông tin thiếu có thể làm thay đổi quyết định căn bản, để trạng thái thiếu bằng chứng thay vì ép nhãn 0 hoặc 1.
6. Ghi ít nhất một trích đoạn nguyên văn từ mỗi phía và rationale giải thích cách nối hai bằng chứng. Với yếu tố vắng mặt, trích đoạn liên quan có thật và nói rõ “CV không cung cấp bằng chứng về…”, không viết một câu giả rồi đặt trong dấu trích dẫn.

## Nhãn và trạng thái

| Kết quả | Cách sử dụng |
|---|---|
| **0 — Không phù hợp** | Có căn cứ lệch nhiệm vụ cốt lõi hoặc không đáp ứng một điều kiện chuyên môn bắt buộc quan trọng. Khác title hoặc không thấy một skill chưa đủ để gán 0. |
| **1 — Phù hợp một phần** | Có liên quan thực chất và bằng chứng cho một phần nhiệm vụ/skill cốt lõi, nhưng còn khoảng thiếu đáng cân nhắc. Phải giải thích vì sao vẫn đáng cân nhắc ở mức một phần. Đây không phải nhãn mặc định khi không biết. |
| **2 — Phù hợp cao** | Bằng chứng rõ về vai trò/nhiệm vụ, kỹ năng cốt lõi và yêu cầu bắt buộc đã xác định; không còn khoảng thiếu quan trọng chưa giải quyết. Thiếu một ưu tiên đơn thuần không tự loại nhãn 2. |
| **`needs_review`** | Yêu cầu mơ hồ, mâu thuẫn, rubric chưa quy định hoặc reviewer không đủ chuyên môn để kết luận. **Để trống nhãn** và ghi điều cần người có chuyên môn phân xử. |
| **`insufficient_evidence`** | Nội dung không đủ bằng chứng cho một kết luận đáng tin cậy. **Để trống nhãn**, nêu thông tin còn thiếu từ CV/JD. |
| **Chưa chấm** | Giữ toàn bộ trường trả lời trống. Ô trống không phải 0. |

Nhãn 0/1/2 dùng `label_status=completed`. “Completed” chỉ nghĩa reviewer đã điền đánh giá, không nghĩa nhãn đã được chuyên gia xác minh, đã phân xử hoặc trở thành gold.

## Kinh nghiệm và điều kiện cần hiệu chỉnh

- Đọc thời lượng cùng nhiệm vụ/phạm vi có bằng chứng. Không cộng công việc song song thành gấp đôi thời gian. Khi lịch làm việc chồng nhau hoặc chỉ ghi năm, ghi khoảng chắc chắn và phần không biết trong rationale.
- “Từ 2 đến 3 năm” tạm hiểu tối thiểu 24 tháng; “trên 3 năm” trong baseline được quy ước 37 tháng theo độ phân giải tháng. Đây là **giả định cần chuyên gia duyệt**, không phải chân lý áp cho mọi JD.
- Thiếu một tháng không tự thành nhãn 0. Xem điều kiện có thật sự bắt buộc, cách viết có chính xác và bằng chứng thời gian có đủ phân giải hay không; chưa rõ thì `needs_review`.
- Thực tập, bán thời gian, dự án học tập không tự quy đổi thành số tháng full-time. Rubric hiện chưa chốt hệ số quy đổi; ghi đúng loại kinh nghiệm và đưa câu hỏi vào calibration.
- Không lấy toàn bộ năm kinh nghiệm nghề để gán cho từng công nghệ. Không tự cộng các scope chồng nhau. Kinh nghiệm chưa rõ giữ unknown, không điền 0 tháng để thay thế.
- Kỹ năng chuyển đổi, yêu cầu ngôn ngữ/chứng chỉ bắt buộc và phạm vi nghề ngoài chuyên môn của reviewer phải được giải thích hoặc đưa ra phân xử. Điều kiện phi chuyên môn không được đưa vào nhãn; JD chứa điều kiện đó có thể cần cờ `needs_review` để điều phối xử lý.

## Điền phiếu CSV

Chỉ sửa **bản sao** `review.csv` của mình. Giữ nguyên mọi dòng, `pair_id`, `reviewer_slot`, `rubric_version`, `cv_version`, `job_version`, `cv_text`, `jd_text`. Phiếu đã xáo thứ tự; đừng tìm nhãn qua ID/hash. Không sửa nội dung CV/JD trong khi chấm.

| Trường trả lời | Quy định |
|---|---|
| `annotator_id` | Mã ổn định của chính người thực hiện, do điều phối cung cấp; A/B chỉ là slot giao phiếu, không thay danh tính reviewer. |
| `annotation_origin` | Người tự đọc/chấm độc lập điền `human_independent`. Công cụ có thể nhận `ai_draft` để phát hiện/loại khỏi thống kê độc lập; không đổi nhãn AI thành nhãn người. `human_adjudicated` chỉ dùng ở phiếu phân xử riêng. |
| `label_status` | `completed`, `needs_review` hoặc `insufficient_evidence`; chưa đọc thì giữ toàn bộ trường trả lời trống. |
| `relevance_0_1_2` | 0/1/2 khi completed; trống khi chưa đủ căn cứ/chờ xem lại. |
| `cv_evidence`, `jd_evidence` | Mỗi ô là một đoạn trích nguyên văn, liên tục, không rỗng từ đúng văn bản tương ứng; giữ dấu và ký tự. Không thêm dấu ngoặc kép vào nội dung ô nếu văn bản gốc không có. Các dẫn chứng bổ sung mô tả trong rationale. |
| `rationale` | Giải thích vai trò, skill cốt lõi, điều kiện bắt buộc/ưu tiên, kinh nghiệm, khoảng thiếu/unknown và vì sao ra kết quả đó. Bắt buộc cả với hai trạng thái chưa kết luận. |
| `reviewed_at` | Thời gian thực tế, ISO 8601 có múi giờ, ví dụ `2026-11-12T15:00:00+07:00`; không dùng thời gian ví dụ nếu không phải lúc chấm. |

CSV có văn bản nhiều dòng; dùng trình đọc CSV đúng định dạng và lưu UTF-8. Không biến hash/ID thành số hoặc chỉnh các cột bất biến. Điều phối sẽ kiểm schema, bằng chứng và phiên bản; công cụ chỉ xác minh trích đoạn có trong text, không tự xác nhận lý luận chuyên môn đúng.

## Ví dụ hiệu chỉnh — chưa phải nhãn gold

- CV ghi đã xây REST API Python/Django và PostgreSQL trong hai năm; JD yêu cầu nhiệm vụ/kỹ năng tương ứng, kinh nghiệm hai năm, Redis là ưu tiên. Cần bàn xem bằng chứng đáp ứng các điều kiện bắt buộc khác chưa; không tự hạ nhãn chỉ vì không thấy Redis.
- CV Python backend gặp JD phân tích kinh doanh cần SQL, Power BI, dashboard và giải thích KPI. Python chung không đủ; phải xét bằng chứng về nhiệm vụ phân tích. Nếu không đủ nội dung để phân biệt “chưa biết” với “lệch nhiệm vụ”, ghi câu hỏi calibration.
- CV ghi DevOps 24 tháng, JD ghi DevOps tối thiểu 60 tháng. Chênh 36 tháng là một bằng chứng về khoảng thiếu, chưa tự quyết định nhãn nếu mức bắt buộc/mô tả thời gian còn mơ hồ.
- CV liệt kê AWS nhưng không nói đã vận hành AWS bao lâu; JD yêu cầu ba năm AWS. Không suy 24 tháng AWS từ hai năm DevOps; ghi phần thiếu bằng chứng.
- JD vừa ghi “Junior, không cần kinh nghiệm” vừa ghi “bắt buộc trên 5 năm” ở yêu cầu. Đưa `needs_review`, nêu hai câu mâu thuẫn; không chọn câu có lợi để chấm.

Không có nhãn số được điền sẵn cho các ví dụ này. Người có chuyên môn cần thảo luận, sửa rubric và ghi phiên bản/lý do thay đổi trước khi dùng làm quy tắc chính thức.

## Độc lập, đối chiếu và phân xử

Reviewer A/B chỉ nhận thư mục phiếu của mình và hướng dẫn này. Không xem nhãn AI/rationale AI, score/rank, manifest chọn mẫu, phiếu hoặc câu trả lời người kia. Nếu đã xem tài liệu có thể ảnh hưởng quyết định, báo điều phối trước khi chấm để ghi hạn chế hoặc bố trí người khác. Hai người độc lập phải là hai người thật; công cụ không xác minh được điều này chỉ từ ID.

Sau khi nộp độc lập, điều phối đóng băng hai CSV gốc và tính đồng thuận trên cặp **cả hai đã completed, có nhãn số và origin human_independent**. Báo riêng chưa chấm/thiếu bằng chứng/needs_review; không biến chúng thành 0. Kappa dùng trọng số quadratic trên 0–1–2; không đủ cặp hoặc phương sai biên bằng 0 có thể không xác định. Không có ngưỡng kappa tự biến dữ liệu thành gold.

Người thứ ba có chuyên môn đọc bằng chứng và hai đánh giá, điền phiếu phân xử riêng: người phân xử, `human_adjudicated`, trạng thái cuối, nhãn cuối hoặc để trống khi chưa rõ, evidence hai phía, lý do và thời gian. Không lấy trung bình/làm tròn hai nhãn. Giữ nguyên hai phiếu gốc và bất đồng trước phân xử. Bất đồng có hệ thống cần sửa rubric trên development rồi chấm lại phần bị ảnh hưởng; không dùng calibration làm final test.

**Bước cần con người tiếp theo:** duyệt rubric và các quy ước kinh nghiệm, phân công hai reviewer đúng chuyên môn, chấm độc lập, xem báo cáo bất đồng, phân xử và quyết định phiên bản rubric tiếp theo. Hiện mới hoàn thành công cụ; chưa có nhãn đã xác minh.
