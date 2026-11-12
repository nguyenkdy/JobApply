# Thử CV–JD: 50 JD và 6 CV giả lập

Đã chạy keyword overlap và BM25 trên 50 JD chọn từ jobs_matching.csv. Đây là thử nghiệm offline;
chưa gắn vào chức năng upload CV của web, chưa import JD vào database, chưa train classifier/LTR.
Chưa có nhãn phù hợp do người đánh giá cung cấp, nên chưa tính Recall@k/NDCG@k.

## Chạy trên VM hoặc máy cá nhân

Giải nén gói, mở terminal tại thư mục có run_bm25.py rồi chạy:

```bash
python3 run_bm25.py --jobs jobs_pilot.csv --cvs cvs_synthetic.csv --output-dir results
```

Windows có thể dùng python thay python3. Python 3.9+, không cần pip, GPU, Docker, internet hay API key.
Script in Top 5 của từng CV; kết quả cũng nằm trong results/top_matches.csv.
Chạy một CV giả lập:

```bash
python3 run_bm25.py --jobs jobs_pilot.csv --cv-text synthetic_cv_texts/CV_SYN_01.txt --top-k 5 --output-dir results_one_cv
```

Đầu vào hiện là CSV/TXT chuyên môn. Chưa có trích xuất PDF, OCR hay ẩn danh CV tự động.
Chỉ dùng CV giả lập hoặc đã ẩn danh; không nối toàn bộ hồ sơ thật vào cv_text.

## Chọn JD và kiểm tra nội dung

Nguồn: ITViec 22, LinkedIn 16, TopCV 12. Cùng nhóm mô tả trùng chính xác chỉ giữ một đại diện.

| Nhóm chọn mẫu | Số JD |
|---|---:|
| Backend Python | 10 |
| Backend Java | 10 |
| Frontend | 10 |
| DevOps / Cloud và role kết hợp | 8 |
| QA / Testing | 8 |
| Data Analyst | 4 |

Nhóm này chỉ phục vụ chọn mẫu; không phải nhãn relevance và không đưa vào bộ chấm điểm.
Có các role kết hợp, như PHP Fullstack yêu cầu DevOps/AWS, để kiểm tra nhầm lẫn khi trùng kỹ năng.
Nhóm Data Analyst chỉ có 4 tin, đều từ ITViec; bộ thử không đại diện cho thị trường hoặc phân bố nguồn.
Phần lớn tin lấy từ các bản trích xuất có đề mục rõ và chưa bị gắn cờ. Một JD Data Analytics
được phục hồi nhiệm vụ từ bản nguồn vì bộ tách mục bỏ sót. Các ID đã cố định trong selection_manifest.csv
trước khi chạy ranking; không lựa lại JD để cải thiện thứ hạng sau khi xem điểm.

Đã rà các phần nhiệm vụ/yêu cầu của 50 JD bằng trợ lý và ghi 21 thao tác sửa trong pilot_edits.csv.
Đây không phải duyệt tay bởi chuyên gia tuyển dụng hay nhãn human gold. Bản nguồn vẫn nguyên vẹn.
Các sửa gồm loại yêu cầu “ưu tiên các ứng viên trẻ từ 2000” bị regex trước bỏ sót; loại điều kiện
“Non-smoker”, phần giới thiệu công ty, thông báo riêng tư, metadata lương/địa điểm trong tiêu đề.
Yêu cầu chuyên môn về ngôn ngữ giao tiếp, chứng chỉ và kinh nghiệm được giữ lại.
Nguồn có thể chứa JD đã hết hạn; chỉ dùng cho nghiên cứu/demo, không mô tả chúng là tin đang tuyển.

## CV giả lập và kết quả Top 1

Mỗi CV có summary, skills, kinh nghiệm, dự án và năng lực ngoại ngữ; không có tên người, tuổi,
giới tính, địa chỉ, email hoặc số điện thoại. Các kỹ năng/dự án là tình huống giả lập.
CV được viết theo hồ sơ nghề nghiệp chung, không sao chép JD để làm đáp án.

| CV | Hồ sơ giả lập | JD đứng đầu | BM25 |
|---|---|---|---:|
| CV_SYN_01 | Backend Python/Django, 2 năm | Python Developer | 72.746 |
| CV_SYN_02 | Data Analyst, 2 năm | Senior MIS Specialist (Data Analyst, SQL, Python, Java) | 67.861 |
| CV_SYN_03 | Backend Java, 3 năm | Python Developer | 49.833 |
| CV_SYN_04 | Frontend React, 1 năm | Junior Frontend Developer | 57.682 |
| CV_SYN_05 | DevOps, 2 năm | Devops Engineer | 83.424 |
| CV_SYN_06 | QA Automation, 2 năm | Tester | 55.701 |

Điểm BM25 không phải phần trăm phù hợp và không so sánh trực tiếp giữa các CV khác nhau.
Top 5 đầy đủ: results/top_matches.csv. Tất cả 300 điểm và thứ hạng: results/rankings_all.csv.
Cột rank_keyword là thứ hạng theo số token chung; rank_bm25 là thứ hạng BM25.
Các từ đóng góp lớn nhất nằm ở top_matching_terms và term_contributions_json.

Với CV Python/Django 2 năm, JD Python Developer đứng hạng 1; JD Data Analyst cao nhất đứng hạng 13:
Senior MIS Specialist (Data Analyst, SQL, Python, Java). Đây chỉ là một ví dụ, không chứng minh độ chính xác.

Các lỗi đã quan sát và giữ nguyên:

- CV Backend Java có JD Python Developer ở hạng 1.
- CV Backend Python có Tester và Junior Frontend trong Top 5.
- CV Data Analyst 2 năm có Senior MIS yêu cầu tối thiểu 3 năm ở hạng 1.
- CV QA Automation có nhiều JD kiểm thử thủ công ở trên JD automation.

Từ chung như “kiểm thử”, “xử lý”, “dữ liệu”, “dự án” và chênh lệch ngôn ngữ Việt/Anh ảnh hưởng mạnh.
BM25 này chưa so sánh số năm, phân biệt kỹ năng bắt buộc/ưu tiên theo logic,
hoặc kiểm tra các chứng chỉ và ngoại ngữ bắt buộc. Không sửa điểm hay thêm boost role sau khi xem kết quả.

## Cách chấm điểm

Chỉ match_text và cv_text được token hóa. Không dùng company, site, URL, ID, nhóm chọn mẫu,
target_role hoặc experience_months làm feature. ID chỉ dùng để sắp xếp khi bằng điểm.
Chuẩn hóa Unicode, chữ thường và một số alias như ReactJS → React, NodeJS → Node.js,
Golang → Go, Power BI → PowerBI. Giữ riêng Java/JavaScript, C++/C#, React/React Native.
Token tiếng Việt hiện tách theo khoảng trắng và ký tự, chưa dùng bộ tách từ tiếng Việt;
đây là hạn chế của baseline cần đo riêng khi cải tiến.

Keyword baseline đếm số token khác nhau chung giữa CV và JD. BM25 dùng k1=1.5, b=0.75:

```text
idf(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score = sum(idf(t) * tf(t,d) * (k1+1)
            / (tf(t,d) + k1 * (1-b + b*len(d)/avg_len)))
```

Mỗi token query chỉ tính một lần. Không có huấn luyện có giám sát.
Truy vấn không có token chung trả Top rỗng thay vì gợi ý tùy ý các JD có điểm 0.

## Kiểm tra thông tin nhạy cảm và proxy

Chạy lại:

```bash
python3 audit_pilot.py --jobs jobs_pilot.csv --cvs cvs_synthetic.csv --output-dir results
```

Đã thử 30 cặp biến thể giả lập: đổi giới tính, tuổi, địa chỉ, tên hoặc tên trường trong khi giữ
phần chuyên môn giống nhau. Khi metadata ở cột riêng và chỉ cv_text chuyên môn được đưa vào
bộ chấm điểm, cả 30 cặp giữ nguyên điểm. Đây chỉ kiểm tra danh sách cột được dùng.

Trong thử nghiệm cố ý nối thông tin đó vào văn bản CV, **9/30 cặp đổi thứ tự Top 5**
và **2/30 cặp đổi Top 1**. Thay tên ảnh hưởng 3/6 cặp, địa chỉ 2/6, tên trường 4/6.
Giới tính/tuổi không đổi Top 5 trong 6 cặp mỗi loại này, không có nghĩa là hết bias.
Chi tiết: results/fairness_probe.csv và results/audit_report.json.
Đây là kiểm tra nhạy cảm trên mẫu nhỏ, không phải chứng nhận công bằng hay đánh giá nhóm dân số.
Nó cho thấy cần trích chuyên môn/ẩn danh trước khi tích hợp upload CV, kể cả với BM25.

## Hard negatives và đánh giá tiếp

results/hard_pair_candidates.csv có 21 cặp khó đề xuất: điểm từ khóa cao nhưng khác nhóm nghề,
hoặc cùng kỹ năng nhưng chênh kinh nghiệm. Nhãn đều để trống; khác role không tự động nghĩa là negative.
results/judgments_template.csv có 300 cặp CV–JD đã xáo trộn, không kèm score hoặc gợi ý nhãn.
Người đánh giá có thể dùng rubric: 0 = không phù hợp về chuyên môn, 1 = phù hợp một phần,
2 = phù hợp tốt; ghi căn cứ từ CV/JD và cách xử lý thiếu thông tin.

Các cặp này dùng để khám phá/hiệu chỉnh baseline; khi đã xem kết quả thì không gọi chúng là test độc lập.
Bước tiếp là chạy embedding đa ngôn ngữ trên cùng 50 JD và 6 CV để so sánh, rồi chuẩn bị
bộ nhãn độc lập lớn hơn. Chia theo CV gốc/template và nhóm JD gần trùng trước khi train classifier/LTR.
Muốn tính Recall@k cần định nghĩa rõ relevant và tập JD đã được đánh giá; NDCG@k dùng mức nhãn
đã thống nhất. Chưa công bố hai chỉ số khi chưa có nhãn phù hợp được duyệt.

## Nội dung gói

- jobs_pilot.csv: 50 JD; chỉ match_text đưa vào scorer.
- cvs_synthetic.csv và synthetic_cv_texts/: 6 CV giả lập ở dạng bảng và TXT.
- run_bm25.py: chạy keyword/BM25 và xuất thứ hạng.
- audit_pilot.py: kiểm tra biến thể thông tin nhạy cảm.
- selection_manifest.csv, prepare_pilot.py, pilot_edits.csv: truy vết và tái tạo tập chọn.
- results/: kết quả đã chạy, cặp khó chưa gán nhãn và mẫu đánh giá trống.

Tái tạo dữ liệu từ hai CSV cũ:

```bash
python3 prepare_pilot.py --matching /path/to/jobs_matching.csv --clean /path/to/jobs_clean.csv --output-dir .
```

prepare_pilot.py ghi đè file pilot cùng tên; không sửa input gốc.
run_bm25.py ghi đè kết quả xếp hạng, nhưng giữ judgments_template.csv nếu file đó đã tồn tại.

Đã kiểm tra công thức BM25 bằng một ví dụ tính độc lập, bảo toàn các token kỹ thuật,
thứ tự điểm, 300 cặp/30 kết quả Top 5, truy vấn không có từ chung và việc loại metadata khỏi feature.
Đây là kiểm tra chức năng, không thay thế đánh giá chất lượng ranking bằng nhãn độc lập.
