# JobApply — Huấn luyện, đánh giá và chạy Top 5 với kinh nghiệm

Giải nén gói vào D:\jobapply_pilot_v1. Chạy các lệnh dưới đây bằng PowerShell từ thư mục này. Gói bổ sung cho pilot đã có, sử dụng jobs_pilot.csv, cvs_synthetic.csv, judgments_ai_draft.csv và results/embedding_vs_bm25.csv trên máy bạn. File nhãn có tên khác có thể chỉ định bằng --labels. Demo E5 sử dụng compare_embeddings.py và run_bm25.py trong thư mục pilot.

~~~powershell
cd D:\jobapply_pilot_v1
& .\.venv-embedding\Scripts\python.exe .\jobapply_experience_v2\run_experiment.py
& .\.venv-embedding\Scripts\python.exe .\jobapply_experience_v2\recommend.py --cv-id CV_SYN_05
~~~

Lệnh đầu train và đánh giá trên điểm đã có, không tải model E5. Lệnh sau minh họa suy luận với classifier v2 đã refit trên 300 cặp, sử dụng E5 trên máy bạn. Top 5 minh họa với CV cũ khác với dự đoán giữ riêng dùng tính chỉ số. Để thử một CV giả lập hoặc đã ẩn danh mới, dùng --cv-text duong_dan.txt và tùy chọn --months duong_dan.json. File TXT chỉ chứa chuyên môn. Ví dụ JSON cho CV có bằng chứng vận hành AWS trong 24 tháng ở vị trí DevOps là {"DevOps":24,"DevOps on AWS":24}. Tên phạm vi nằm trong jd_experience.csv. Chỉ điền thời lượng có bằng chứng. Công cụ chạy offline trên 50 JD, chưa gắn vào giao diện hoặc database web.

## Dữ liệu và đặc trưng

jd_experience.csv và cv_experience.csv là phần chú thích kinh nghiệm cho pilot, do trợ lý đọc yêu cầu và mô tả chuyên môn. Đây là chú thích riêng cho 50 JD và 6 CV giả lập. Khi dùng với JD/CV khác, cần trích các trường tương ứng. Số năm đến từ kinh nghiệm chuyên môn, loại tuổi, ngày sinh, địa chỉ, năm tốt nghiệp và thời lượng hợp đồng.
- Với ngưỡng “từ 2 đến 3 năm”, lấy 24 tháng tối thiểu. “Trên 3 năm” lấy 37 tháng tối thiểu theo độ phân giải tháng. Các cách diễn đạt số năm chưa rõ ngưỡng được diễn giải như mức tối thiểu cho pilot; lưu câu gốc để rà lại.
- Chỉ so thời lượng cho phạm vi nghề hoặc kỹ năng tương ứng có bằng chứng. Có một kỹ năng trong danh sách chưa đủ để gán toàn bộ số tháng làm việc cho kỹ năng đó.
- Khi có nhiều mốc, lấy mức thiếu lớn nhất trong các điều kiện so được. Coverage là tỷ lệ điều kiện có thể so. Ghi trống gap_months_observed khi chưa biết; tại đầu vào mô hình ghép 0 với coverage=0. Trường hợp đã đủ thời gian có gap=0 và coverage dương.
- CV DevOps 24 tháng gặp JD tối thiểu 5 năm DevOps có gap=36 tháng. Điều kiện chưa rõ phạm vi, lịch thực tập hay “a few years” không tự đặt mốc.

## Đọc kết quả

Script huấn luyện 6 lượt, mỗi lượt giữ toàn bộ 50 cặp của một CV để đánh giá. Scaler chỉ fit trên phần train. BM25, embedding, classifier gốc 2 đặc trưng, classifier thêm coverage và classifier thêm cả coverage/gap được chấm theo cùng chia tập và cùng nhãn. Recall@5 coi nhãn 2 là phù hợp tốt; NDCG@5 dùng gain 2^label - 1. Macro tính theo CV. So experience_classifier với coverage_control để tách tác động của mức thiếu kinh nghiệm khỏi tác động của khớp phạm vi. Sau khi đánh giá mới refit classifier v2 cho demo.

results/experience_v2 chứa macro_metrics.csv, metrics_by_cv.csv, held_out_predictions.csv, experience_pairs.csv, run_info.json và experience_classifier.joblib. Cột rank_classifier cũ được thay bằng các cột rank_base_classifier, rank_coverage_control, rank_experience_classifier trong kết quả v2. Điểm dự đoán là kỳ vọng nhãn 0..2.

## Kiểm tra đã chạy

Đối chứng riêng bằng BM25 và kinh nghiệm (không dùng E5) có kết quả trong lexical_control_metrics.csv. Có 41/50 JD với mốc số, 4 JD nhiều điều kiện, 45/300 cặp có phạm vi so được và 28 cặp thiếu thời gian trong số điều kiện đo được. Ở chế độ này NDCG@5 đạt 0,4493 với BM25, 0,7009 khi classifier biết coverage và 0,7812 khi thêm độ thiếu. Có thể tái lập bằng run_experiment.py --lexical-check, sau đó recommend.py --lexical-check --cv-id CV_SYN_05.

Chỉ số này thuộc pilot phát triển: 6 CV giả lập, cùng kho JD, nhãn AI mà người dùng đã xem. Các yêu cầu này và một số lỗi xếp hạng đã được khảo sát khi thiết kế đặc trưng; cần tập CV/JD độc lập và nhãn độc lập cho kết luận ngoài pilot. Các phép kiểm tra fairness trước đó dành cho BM25. Bản E5/classifier và luồng đọc PDF cần kiểm tra riêng khi tích hợp web.
