# Kiểm toán Bước 1–3 và điều kiện Bước 4 — 14/11/2026

**Chưa huấn luyện hoặc chốt model.** Run `ml_data_runs\20261113_benchmark_v2\run_08` có đủ artifact và hash hợp lệ, nhưng split chưa tách được quan hệ template lịch sử. Không có yêu cầu người review trong pipeline hiện hành. [Receipt](reports/20261114-benchmark-audit.json).

## Những gì đã kiểm chứng và sửa

1. **Metadata JD:** số 96% là 48/50 nghề khớp nhóm pilot development. Con số 100% là phát hiện *có ngưỡng kinh nghiệm*, không phải đúng mọi số tháng/scope; kiểm tra cũ chỉ khớp ít nhất một giá trị ngưỡng trên 40/41 trường hợp (97,56%). Đã bỏ suy scope công nghệ từ chức danh/tổng năm, bỏ upper bound/ưu tiên khỏi minimum, không gộp nhiều thời lượng trên cùng dòng khi chưa xác định được scope. Điều kiện tùy chọn không còn được tính như kỹ năng cốt lõi. Bộ mới `jd-rule-extractor-v2-conservative` có độ phủ trên 788 JD: `{'missing_experience': 286, 'missing_role': 308, 'missing_skills': 95, 'missing_stack': 172, 'total': 788, 'with_experience': 502, 'with_role': 480, 'with_skills': 693, 'with_stack': 616}`. Chưa khẳng định độ chính xác ngoài development.
2. **CV và split:** 49/60 CV đổi họ template v1→v2; 41 trong số đó giữ nguyên các đoạn nội dung. Có 6 họ gốc đi qua nhiều partition trong split cũ. Sau khi nối cả họ gốc và họ v2, có **1 nhóm, kích thước [60]**. Không sửa source/provenance hoặc đổi seed để ép thành 30/20/10. Preview kỹ thuật hiện là `{'train': 60}`; không phải split huấn luyện đã chấp nhận.
3. **Nhãn:** bỏ công cụ calibration, không yêu cầu người chấm. Giữ kiểm tra hash/schema/evidence. Nhãn là `automatic_rule_proxy`, không phải gold độc lập. Nghề không rõ hoặc không đủ bằng chứng để kết luận giữ `insufficient_evidence` và ô nhãn trống; không đổi thành 0. Không lấy max tháng khác scope, không quy thực tập/dự án thành kinh nghiệm nghề, không cho thiếu 3 tháng thành đã đủ; xử lý cận `>` riêng `>=`. Mọi kết quả sửa nhãn là output mới, giữ bản cặp nguồn.

| Danh sách cặp được kiểm toán | Tổng | Có nhãn proxy | Chưa đủ bằng chứng | Phân bố 0/1/2 |
|---|---:|---:|---:|---|
| train cũ | 308 | 246 | 62 | `{'0': 115, '1': 131}` |
| validation cũ | 1000 | 977 | 23 | `{'0': 800, '1': 176, '2': 1}` |
| test cũ | 500 | 485 | 15 | `{'0': 400, '1': 84, '2': 1}` |

Train cũ hiện không còn nhãn 2 theo quy tắc đã sửa, nên chưa đủ lớp cho thí nghiệm 0/1/2 dự kiến. Tổng 100 cặp giữ trống vì thiếu bằng chứng; không ép thành nhãn để đạt 100%.

Bộ trích xuất mới giữ unknown thận trọng hơn: trên development, phát hiện ngưỡng có precision `1.0`, recall `0.9024`, khớp max giá trị `36/41` (`0.878`). Đây là đánh đổi quan sát được, **không công bố quy tắc mới chính xác hơn về ngữ nghĩa**. Các trường hợp nhiều mệnh đề/thời lượng cần cách biểu diễn tốt hơn trong phiên bản sau.

Các bảng trên sửa nhãn của danh sách cặp **cũ**, chỉ phục vụ chẩn đoán. Chúng không trở thành train/validation/test hợp lệ sau khi sửa nhãn. 30 cặp đối chứng cũ được giữ trong snapshot lịch sử; không chạy lại và không cần để mở khóa training.

## Dữ liệu và bảo toàn

Kho JD vẫn 3.062 record: 888 keep, 65 trùng loại, 2.109 quarantine; 100 keep development, **788 keep ngoài development**. Toàn bộ 154 record thuộc nhóm development giữ nguyên. Danh sách 50 JD cũ được giữ nguyên ID; không chọn lại theo nhãn mới. Nó là tập con được chọn, không đại diện tự động cho hiệu quả truy hồi trên cả 788 JD hoặc thị trường.

Giữ nguyên byte 3 CSV gốc, 51 file pilot theo Git và run benchmark cũ. Dữ liệu dẫn xuất nằm trong `ml_data_runs/20261114_benchmark_audit_02`, gồm metadata JD/evidence, CV với ancestry snapshots, dataset/group, preview và ba thư mục `diagnostic_*_labels`. Chưa đổi API/UI/Docker/VM, chưa tạo model package.

**Data Analyst vẫn thuộc nghiên cứu:** 9 tag nguồn, 8 dấu hiệu chức danh, 4 nối pilot, 0 JD ngoài pilot qua gate ở nhóm kiểm kê này. Cần bổ sung/khôi phục JD hợp lệ, giữ lô sửa parser ở development, trước khi đưa nghề này vào benchmark mới.

## Bước 4 sau khi dữ liệu đủ điều kiện

- Bổ sung các họ CV có nguồn/khung độc lập thực sự; tối thiểu 3 nhóm để có ba partition, nhưng 1 họ ở mỗi tập vẫn rất yếu. Thiết kế đa dạng nghề và loại kinh nghiệm *trước* khi viết CV mới; không đổi họ các CV cũ để cân bằng. Lô 60 CV hiện tại giữ nguyên toàn nhóm và nên dùng development.
- Sửa phần metadata/nhãn thiếu bằng chứng bằng quy tắc có evidence hoặc giữ chưa có nhãn; không điền âm tính để đạt 100%. Chưa thể báo Recall@5 đầy đủ trên catalog nếu bỏ qua cặp chưa có nhãn.
- Khóa catalog/split, phiên bản nhãn tự động và protocol. Fit scaler/Logistic Regression chỉ trên train; so Keyword/BM25/E5/text-only LR/metadata LR và chính baseline luật sinh nhãn trên validation. Baseline luật và ablation cần thiết vì đặc trưng skill/stack/experience cũng đang sinh nhãn, có nguy cơ chỉ học lại chính quy tắc.
- E5 dự kiến `intfloat/multilingual-e5-base`: khóa revision và checksum, prefix query/passage, pooling/chunking và môi trường. Theo [model card chính thức](https://huggingface.co/intfloat/multilingual-e5-base), dùng prefix đúng và giới hạn token đã công bố. Chưa tải/chạy encoder này trong lượt kiểm toán.
- Định nghĩa Recall với nhãn ≥1 và báo thêm nhãn 2; NDCG gain `2^label - 1`; macro theo CV, báo số CV không có positive. Chọn trên validation, ghi lựa chọn bất biến rồi mới đánh giá test. Không dùng kết quả test để đổi nhãn, seed hoặc chọn model.
- Kiểm tra bất biến Top 5 khi đổi tên/tuổi/giới tính/địa chỉ ở trường ngoài văn bản chuyên môn; đây là kiểm tra kỹ thuật loại thông tin cá nhân, **không phải chứng minh công bằng nhân khẩu học**. Chỉ đóng gói artifact sau khi chạy thật và kiểm tra reload/hash.

Synthetic + nhãn tự động có thể dùng làm thí nghiệm nội bộ có giới hạn, chưa chứng minh chất lượng với người dùng thật. Không bắt buộc quy trình người review; các lỗi lineage/unknown/evaluation vẫn phải xử lý.
