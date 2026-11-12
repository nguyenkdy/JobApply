# JobApply — Tiến độ triển khai AI matching CV–JD

Cập nhật ngày 10/11/2026. Báo cáo sử dụng thống nhất **Recall@5 và NDCG@5**.

## 1. Mục tiêu

Xây dựng chức năng để ứng viên upload CV lên JobApply và nhận danh sách công việc phù hợp. Hệ thống cần khai thác kỹ năng, vị trí và kinh nghiệm, thay vì chỉ dựa vào từ khóa trùng nhau.

- Chuẩn hóa skills, title và experience từ CV/JD.
- So sánh BM25, embedding similarity và mô hình học có giám sát để xếp hạng.
- Bổ sung các cặp khó, đánh giá bằng Recall@5 và NDCG@5.
- Kiểm tra ảnh hưởng của giới tính, tuổi, địa chỉ và proxy không phù hợp.
- Demo chỉ sử dụng CV giả lập hoặc đã ẩn danh.

Ví dụ mục tiêu: CV Python/Django có 2 năm kinh nghiệm Backend cần được ưu tiên cho JD Backend phù hợp hơn JD Data Analyst chỉ cùng chứa từ “Python”.

Repo ứng dụng: https://github.com/nguyenkdy/JobApply

## 2. Dữ liệu và công việc đã thực hiện

### 2.1. Nguồn dữ liệu JD

Bộ dữ liệu thực tế dùng trong quy trình này là **Vietnamese IT Job Posting Data**, từ https://github.com/SonPhatTranDeveloper/IT-Job-Posting.

- File gốc: `job_descriptions.csv`, gồm **3.101 JD**.
- Nguồn tin: LinkedIn 1.039, ITViec 929, TopCV 1.133.
- Có chức danh, công ty, mô tả, địa điểm, nền tảng và URL nguồn.
- Các trường công nghệ được trích xuất bằng LLM ở nguồn chưa được xem là nhãn chuẩn đã xác minh.

Vietnam Jobs trên Kaggle là nguồn được đề cập ban đầu. Khi báo cáo bộ dữ liệu đang sử dụng, ghi nguồn GitHub phía trên. Dữ liệu JD lịch sử đang phục vụ nghiên cứu offline, chưa được nhập toàn bộ vào database thành tin đang tuyển.

### 2.2. Làm sạch và chuẩn bị văn bản

1. **`jobs_clean.csv` — 3.062 JD:** chuẩn hóa Unicode, khoảng trắng, giá trị thiếu và một số tên công nghệ. Tách 38 bản ghi trùng và 1 mô tả quá ngắn. Giữ dữ liệu nguồn để truy vết.
2. **`jobs_matching.csv` — 3.062 JD:** tách nhiệm vụ, yêu cầu và ưu tiên; tạo `match_text` từ chức danh và nội dung chuyên môn. Lọc các phần không phục vụ matching và gắn cờ trường hợp cần kiểm tra. Đây chưa phải bước gán nhãn phù hợp.
3. **`jobs_pilot.csv` — 50 JD:** chọn mẫu theo nhóm nghề, tránh mô tả trùng chính xác và rà lại nội dung. Việc rà soát bằng trợ lý chưa tương đương xác minh bởi chuyên gia tuyển dụng.

Bộ pilot gồm Backend Python 10, Backend Java 10, Frontend 10, DevOps/Cloud và vị trí kết hợp 8, QA/Testing 8, Data Analyst 4. Có 22 tin ITViec, 16 LinkedIn và 12 TopCV. Đây là mẫu có chủ đích, chưa đại diện thị trường.

### 2.3. CV giả lập và nhãn thử nghiệm

- Tạo **6 CV giả lập** trong `cvs_synthetic.csv`, thuộc sáu nhóm nghề tương ứng.
- Mỗi CV ghép với 50 JD, tạo **300 cặp CV–JD**.
- `judgments_ai_draft.csv` chứa `cv_id`, `job_id`, `relevance_0_1_2`, `reviewer`, `rationale`.
- Nhãn **0**: không phù hợp; **1**: phù hợp một phần; **2**: phù hợp cao.
- Nhãn được đề xuất từ nội dung CV/JD, xét vai trò, kỹ năng, kinh nghiệm và yêu cầu quan trọng. Không quy đổi trực tiếp điểm BM25/cosine thành nhãn.

**Giới hạn:** AI hỗ trợ đề xuất nhãn và người thực hiện đã xem lại, nhưng chưa có xác minh độc lập theo một quy trình gán nhãn được thống nhất đầy đủ. Nhãn hiện dùng cho thử nghiệm ban đầu, chưa phải bộ chuẩn tuyển dụng.

## 3. Phương pháp đã chạy

### 3.1. BM25 và embedding

- **BM25:** chấm điểm theo từ khóa chung, độ hiếm của từ và độ dài JD.
- **Embedding:** dùng `intfloat/multilingual-e5-small` trên CPU để tạo vector CV/JD và tính cosine similarity. Chưa fine-tune E5.
- Văn bản vượt giới hạn 512 token được chia đoạn và tổng hợp vector để giảm việc bỏ mất nội dung.
- Cùng dùng `cv_text` và `match_text` để so sánh trên cùng bộ dữ liệu.
- `compare_embeddings.py` tạo `results/embedding_vs_bm25.csv`, chứa 300 cặp với điểm và thứ hạng của hai phương pháp.

### 3.2. Classifier cơ bản — mốc đã chạy thành công gần nhất

Đã chạy thành công `train_matcher.py` sau khi xử lý vấn đề định dạng số trong CSV.

- Ghép file điểm và file nhãn theo cả `cv_id` và `job_id`.
- Đầu vào X: **BM25 score và cosine similarity**.
- Mục tiêu y: **nhãn 0–1–2**.
- Mô hình: **StandardScaler + Logistic Regression**.
- Tính điểm xếp hạng từ xác suất: `P(nhãn 1) + 2 × P(nhãn 2)`.
- Model cơ bản không đọc trực tiếp văn bản CV/JD hoặc `rationale`, và **chưa dùng đặc trưng kinh nghiệm riêng**.

Cách đánh giá: mỗi lượt huấn luyện trên 5 CV (250 cặp), giữ riêng 1 CV (50 cặp), lặp lại 6 lượt. Bộ chuẩn hóa được fit trong dữ liệu huấn luyện từng lượt. Danh mục 50 JD vẫn dùng chung giữa các lượt, nên chưa kiểm tra khả năng áp dụng với JD mới.

Sau đánh giá, script huấn luyện lại trên toàn bộ 300 cặp và lưu model cùng các bảng kết quả tại `results/supervised`. Model fit toàn bộ dữ liệu phục vụ chạy thử; các chỉ số bên dưới lấy từ các lượt giữ riêng CV.

### 3.3. Thử nghiệm kinh nghiệm đã có trước đó

Trong các lượt trước của cuộc trao đổi, đã chạy phiên bản `jobapply_experience_v2` và thử `recommend.py --cv-id CV_SYN_05`. Đặc trưng bổ sung biểu diễn khả năng đối chiếu kinh nghiệm cùng lĩnh vực và mức thiếu hụt so với yêu cầu JD.

Ví dụ: CV có 24 tháng DevOps, JD yêu cầu 60 tháng thì thiếu 36 tháng. Nếu không đủ bằng chứng để đối chiếu, ghi chưa biết; không tự coi thiếu thông tin là 0 năm.

Kết quả Top 5 đã gửi trước đó của `experience_classifier`: **Recall@5 = 0,6270; NDCG@5 = 0,7661**. Đây là kết quả của phiên bản riêng, không phải dòng `classifier` trong lần chạy `train_matcher.py` gần nhất. Cần đối chiếu lại dữ liệu, nhãn và phiên bản trước khi dùng làm kết luận chính thức. Phần kinh nghiệm hiện dựa trên dữ liệu chuẩn bị cho pilot, chưa phải bộ trích xuất tổng quát cho CV/JD bất kỳ.

## 4. Kết quả Top 5 hiện được xác nhận

Lần chạy `train_matcher.py` gần nhất cho kết quả trung bình qua 6 CV giữ riêng:

- **BM25:** Recall@5 = **0,3016**; NDCG@5 = **0,4493**.
- **Embedding:** Recall@5 = **0,5476**; NDCG@5 = **0,6748**.
- **Classifier cơ bản:** Recall@5 = **0,5476**; NDCG@5 = **0,6678**.

**Recall@5** là số JD nhãn 2 trong Top 5 chia cho tổng số JD nhãn 2 của CV trong 50 JD. Báo cáo lấy trung bình theo CV. Recall 0,5476 không có nghĩa 54,76% của năm đề xuất đều phù hợp.

**NDCG@5** xét cả mức nhãn và vị trí, thưởng cao hơn khi JD phù hợp nằm đầu danh sách. Script dùng gain `2^nhãn − 1` và giảm trọng số theo vị trí. NDCG 0,6678 không phải Accuracy 66,78%.

Nhận xét: embedding tốt hơn BM25 theo bộ nhãn hiện tại. Classifier cơ bản có Recall trung bình bằng embedding, nhưng NDCG thấp hơn một chút; chưa thể hiện cải thiện. Hai chỉ số dùng để đánh giá đầu ra, không đưa vào làm feature huấn luyện.

Đã thử thêm Top 7 và Top 10, nhưng **báo cáo tiến độ này chỉ dùng Top 5** để thống nhất giữa các phương pháp.

## 5. Trạng thái và giới hạn hiện tại

- Đã hoàn thành một quy trình ML offline từ dữ liệu, so khớp, nhãn thử nghiệm đến huấn luyện và đánh giá.
- App đã được chạy bằng Docker Compose trên VM theo xác nhận của người thực hiện. Chưa hoàn tất tích hợp recommendation vào luồng upload CV của web.
- Có demo recommendation bằng terminal; chạy trên CV đã tham gia huấn luyện chỉ minh họa đầu ra, không thay thế đánh giá độc lập.
- Chưa chốt model cuối cùng. Chạy thành công hoặc đạt điểm cao trên pilot chưa đủ chứng minh chất lượng thực tế.
- 300 cặp chỉ xuất phát từ 6 CV, không phải 300 hồ sơ độc lập. Chưa có tập kiểm tra mới được giữ kín khỏi quá trình chỉnh phương pháp.
- Đã có kiểm tra nhạy cảm sơ bộ với BM25 và các cặp khó đề xuất. Chưa hoàn tất kiểm định thuộc tính nhạy cảm/proxy cho toàn bộ hệ thống và các model.
- Chất lượng nhãn, độ đại diện dữ liệu và độ chính xác trích xuất vẫn cần được cải thiện.

Sự cố đã gặp: chuỗi điểm như `3.647.222` không chuyển được sang số, có khả năng do Excel thay đổi định dạng khi lưu CSV. Sau hướng dẫn tạo lại file điểm, lần chạy huấn luyện tiếp theo đã thành công. Không sửa số bằng cách xóa dấu chấm tùy ý; giữ bản CSV gốc và dùng bản sao khi thao tác trình bày.

## 6. Kế hoạch tiếp theo

### Ưu tiên 1 — Củng cố dữ liệu và nhãn

- [ ] Thống nhất tiêu chí 0–1–2, cách xử lý yêu cầu bắt buộc, yêu cầu ưu tiên và thông tin thiếu.
- [ ] Nhờ người có chuyên môn gán nhãn/kiểm tra độc lập, ghi bằng chứng và xử lý bất đồng.
- [ ] Mở rộng CV giả lập/ẩn danh và JD, bao phủ nhiều mức kinh nghiệm.
- [ ] Bổ sung hard negatives đã xác minh, ví dụ cùng Python nhưng khác nhiệm vụ, hoặc đúng nghề nhưng thiếu điều kiện quan trọng.
- [ ] Giữ riêng tập kiểm tra, kiểm soát CV cùng mẫu và JD gần trùng; kiểm tra cả CV mới và JD mới.

### Ưu tiên 2 — Hoàn thiện xử lý đầu vào và model

- [ ] Trích xuất và chuẩn hóa skills, title, experience từ CV/JD mới, lưu bằng chứng và trạng thái chưa biết.
- [ ] Kiểm chứng lại phiên bản kinh nghiệm và so sánh với BM25, embedding, classifier cơ bản cùng điều kiện.
- [ ] Dùng thống nhất Recall@5 và NDCG@5; chỉ chọn model sau khi xem kết quả và phân tích lỗi trên dữ liệu đủ tin cậy.
- [ ] Thử thay tên, giới tính, tuổi, địa chỉ và proxy trong khi giữ nguyên năng lực; đo thay đổi điểm/thứ hạng. Kiểm tra cả bước trích xuất và model.

### Ưu tiên 3 — Tích hợp và demo JobApply

- [ ] Hoàn thiện luồng upload CV giả lập/ẩn danh và trích xuất văn bản chuyên môn.
- [ ] Xây API recommendation, kiểm tra quyền truy cập CV.
- [ ] Chấm điểm các JD đang mở và chưa hết hạn trong database, trả Top 5 kèm liên kết chi tiết.
- [ ] Kiểm thử toàn bộ luồng: upload CV → trích xuất → chấm điểm → hiển thị đề xuất → xem JD/ứng tuyển.
- [ ] Ghi nhận thời gian xử lý, trường hợp sai và giới hạn của demo.

## 7. Cấu trúc slide báo cáo đã thống nhất

1. **Bài toán đề xuất việc làm theo CV.**
2. **Dữ liệu và quy trình chuẩn bị.**
3. **So khớp và xếp hạng bằng BM25, embedding.**
4. **Gán nhãn và đánh giá Top 5.**
5. **Huấn luyện và đánh giá classifier cơ bản.**
6. **Kế hoạch triển khai tiếp theo.**

Ảnh và kết quả đặt ngay trong phần phương pháp; không cần phần kết quả thực nghiệm riêng. Chỉnh slide/ảnh từng dùng Top 7 hoặc Top 10 về Top 5. Dùng đoạn kết quả classifier thành công gần nhất để minh họa slide 5.

## 8. Lệnh đối chiếu kết quả trên Windows PowerShell

Chạy tại `D:\jobapply_pilot_v1`.

Đánh giá riêng BM25 và embedding ở Top 5:

```powershell
.\.venv-embedding\Scripts\python.exe .\evaluate_topk.py --labels .\judgments_ai_draft.csv --rankings .\results\embedding_vs_bm25.csv --k 5
```

Huấn luyện và đánh giá classifier cơ bản ở Top 5 theo script hiện tại:

```powershell
.\.venv-embedding\Scripts\python.exe .\train_matcher.py
```

Lệnh huấn luyện ghi lại kết quả trong `results\supervised`. Không cần chạy lại nếu dữ liệu và code không đổi, chỉ để tái tạo ảnh báo cáo khi cần. Bash chỉ dùng cho thao tác Linux trên VM chạy Docker Compose.
