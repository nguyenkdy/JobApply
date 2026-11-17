# Kiểm tra sau merge và nguyên nhân thiếu nhãn — 16/11/2026

Đã thực hiện **bước 1 và 2** trên `main`, commit `5d672a6`. Không sửa parser, luật nhãn, CV/JD, lineage, partition hoặc model. Không commit/push. [Receipt tổng hợp](reports/20261116-readiness-audit.json), [bằng chứng checksum](reports/20261116-protected-input-audit.json), [chẩn đoán từng JD](reports/20261116-jd-diagnostics.csv).

## 1. Chênh lệch checksum đã được giải thích

**50/54 file khớp nguyên byte; 4 file mã/lock chỉ khác CRLF và LF.** Chuyển LF thành CRLF trong bộ nhớ tái tạo chính xác SHA256 lịch sử của cả bốn file. Đây là chứng cứ byte, không chỉ là nhận xét “code trông giống nhau”. Ba CSV nguồn và các file dữ liệu pilot vẫn khớp nguyên byte.

| File | Số LF hiện tại | SHA256 lịch sử | SHA256 hiện tại |
|---|---:|---|---|
| `jobapply_pilot_v1/evaluate_top5.py` | 5 | `011fb350711c…` | `0aed3aec401b…` |
| `jobapply_pilot_v1/evaluate_topk.py` | 46 | `c41d13d3befb…` | `37facf302cac…` |
| `jobapply_pilot_v1/jobapply_experience_v2/train_matcher.py` | 9 | `298b4a61f80f…` | `be05973909d2…` |
| `jobapply_pilot_v1/requirements-ml-win-py314.lock.txt` | 45 | `c223fb7aace3…` | `098694d5403f…` |

Các file hiện tại khớp blob Git HEAD. `.gitattributes` trong repo quy định `eol=lf`, đã tồn tại từ trước merge; quan sát này phù hợp với chuẩn hóa checkout. Không có bằng chứng cần sửa logic mã hoặc phiên bản thư viện. Không thể xác định riêng tiến trình/thời điểm đã đổi newline chỉ từ hash; không tuyên bố merge đã đổi thuật toán.

Giữ LF theo repo; **không đổi file về CRLF để làm xanh gate**, không ghi đè checksum trong receipt/run cũ. Báo cáo cũ mô tả byte ở thời điểm tạo run, không còn là chứng nhận byte của mọi file code trong checkout hiện tại. Gate strict `check-expanded-labels` vẫn sẽ báo `Protected originals changed` vì khác byte. Audit mới báo riêng: snapshot hợp lệ, dữ liệu gốc nguyên byte, code chỉ khác newline; **không biến kết quả đó thành strict byte-pass**.

Đã xác minh manifest của 6 run lịch sử, manifest intake v7 và nhãn v1; dựng lại facts từ câu/offset, kiểm lineage/split/census rồi tái tính đúng 48,284 quyết định theo luật đã đóng băng. Các file thực thi so với snapshot được kiểm tương đương CRLF/LF trước khi dùng. Nhãn và source snapshot không bị viết lại.

## 2. Vì sao 43.964 cặp còn trống?

Các nhóm dưới đây **loại trừ nhau**, cộng đúng 43,964 cặp:

| Nguyên nhân trực tiếp theo luật v1 | Số cặp | Tỷ lệ trong cặp trống |
|---|---:|---:|
| Hai nghề khác nhau; luật chưa có căn cứ kết luận mức phù hợp | 25,766 | 58.61% |
| Extractor chưa xác định được một nghề JD rõ ràng | 8,280 | 18.83% |
| Quan hệ nghề được chấp nhận nhưng không có skill trùng chuỗi chính xác | 6,839 | 15.56% |
| JD ngoài phạm vi benchmark phần mềm | 1,704 | 3.88% |
| Nghề JD còn quá chung chung | 1,290 | 2.93% |
| Không có skill JD trong bộ bằng chứng tích cực đã lọc | 85 | 0.19% |

**Điều chỉnh cách hiểu trước đây:** không thể quy toàn bộ ô trống cho parser đọc kém. Nhóm lớn nhất là quan hệ giữa các nghề mà luật chưa có căn cứ chấm phù hợp/không phù hợp. Khác tên nghề không tự chứng minh nhãn 0. “Không có skill trùng chuỗi” cũng không chứng minh không có năng lực chung: metadata có thể thiếu, alias có thể khác, hoặc thực sự khác stack; audit này không đoán thay.

Tất cả 788 JD đều có title, nhiệm vụ và phần yêu cầu không rỗng. Do đó nghề unknown hoặc thiếu skill trích xuất **không đồng nghĩa văn bản JD trống**. Trong 136 JD chưa có nghề rõ: 116 không có candidate từ extractor, 20 có nhiều candidate. 21 JD generic là nhóm riêng. Chưa chứng minh các trường hợp đó đều có một đáp án nghề duy nhất mà chỉ cần sửa regex là lấy được.

Về thông tin thiếu đã xác nhận: 24/120 CV tự khai timeline unknown và không có thời lượng; có 653 JD để trống cột ưu tiên, điều này không tự là lỗi hoặc chứng minh không có ưu tiên trong các cột khác. Không có CV thiếu hoàn toàn skill metadata. Không suy tháng công nghệ từ tổng thời gian làm việc.

### Parser chưa hiểu những gì?

Có **2,293 mệnh đề công nghệ unresolved**, phân loại theo điểm ngữ pháp bị từ chối:

| Cơ chế parser không chấp nhận | Số mệnh đề |
|---|---:|
| `document_guard_disabled_local_parse` | 1 |
| `duration_sentence_not_supported` | 212 |
| `prefix_not_supported` | 1,869 |
| `technology_expression_not_supported` | 211 |

`prefix_not_supported`: câu không bắt đầu bằng một trong số ít mẫu mà luật nhận. `technology_expression_not_supported`: mở đầu được nhận nhưng phần sau không phải danh sách công nghệ đơn giản. `duration_sentence_not_supported`: câu có dấu hiệu tháng/năm nhưng không khớp mẫu scope/ngưỡng hẹp. `document_guard_disabled_local_parse`: câu riêng đọc được nhưng chốt điều kiện ở mức tài liệu chặn.

Có 473 mệnh đề thời lượng unresolved trên 428 JD; chỉ 1 JD có ngưỡng được chấp nhận hoàn chỉnh. Cờ khoảng năm, dấu cộng, “vị trí tương tự”, điều kiện và ngưỡng tối thiểu được lưu riêng. Chúng là dấu hiệu quan sát, không phải nhãn bắt buộc/ưu tiên mới. Bộ phân tích chỉ nhận câu công nghệ bắt buộc đầy đủ ở 5 JD. Điều này mô tả giới hạn bộ luật, không phải số JD thực sự có yêu cầu.

### Vì sao chưa có nhãn 2?

Trong 4,319 cặp đang có nhãn 1, các điều kiện chưa đạt dưới đây **có thể chồng lấn; không cộng lại**:

| Điều kiện còn vướng theo luật v1 | Số cặp nhãn 1 |
|---|---:|
| `mandatory_technology_not_fully_supported` | 37 |
| `no_parsed_mandatory_technology` | 4,277 |
| `no_parsed_required_duration` | 4,313 |
| `required_duration_not_fully_supported` | 5 |
| `role_overlap_not_exact` | 2,136 |
| `unresolved_duration_clause` | 2,296 |
| `unresolved_technical_clause` | 4,214 |

Sửa parser không bảo đảm tất cả những cặp này sẽ thành nhãn 2: CV vẫn có thể thiếu scope/thời lượng/kỹ năng, hoặc chỉ chồng lấn nghề. Kết quả nhãn hiện tại giữ nguyên: 1 nhãn 0, 4.319 nhãn 1, 0 nhãn 2; train chỉ có 257 nhãn 1. Không train và không tính metric full-catalogue từ các ô trống.

## Artifact và cách kiểm lại

Run audit local được lưu vào thư mục mới truyền qua `--output`; `manifest.json` ghi hash toàn bộ kết quả. Đầu vào: `ml_data_runs/20261116_authored_cv_v7_01` và `ml_data_runs/20261116_expanded_labels_v1_01`.

- `protected_input_audit.json`: expected/current hash và chứng minh newline cho từng file.
- `source_execution_audit.json`, `historical_manifest_audit.json`: kiểm mã dùng để tái tính và run lịch sử.
- `unlabeled_pairs.csv`: nguyên nhân trực tiếp của từng cặp trống; không có văn bản CV/JD hoặc nhãn mới.
- `label_one_gaps.jsonl`: các điều kiện ngăn nhãn 1 thành 2, cho phép nhiều cờ trên một cặp.
- `jd_diagnostics.csv`, `unresolved_technical_clauses.jsonl`, `unresolved_duration_clauses.jsonl`: ID/offset/hash để truy câu gốc.
- `development_jd_examples.local.json`: tối đa ba ví dụ mỗi loại từ JD đã dùng phát triển parser; giữ local, không đưa nội dung nguồn vào báo cáo Git.

```powershell
Set-Location D:\JobApply
$auditOut = '.\ml_data_runs\readiness_audit_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data audit-readiness --intake .\ml_data_runs\20261116_authored_cv_v7_01 --labels .\ml_data_runs\20261116_expanded_labels_v1_01 --output $auditOut
if ($LASTEXITCODE -ne 0) { throw 'Readiness audit failed' }
Get-Content (Join-Path $auditOut 'summary.json')
```

## Bước sau — chưa thực hiện trong lượt này

Mở rộng parser trên JD development với fixture riêng, nhưng đồng thời cần thiết kế rõ chính sách quan hệ nghề/kỹ năng và phạm vi benchmark; chỉ sửa mẫu câu không giải quyết toàn bộ ô trống. Giữ riêng vấn đề dữ liệu thiếu, parser không hỗ trợ và quyết định nằm ngoài phạm vi luật. Không tự đánh 0 cho khác nghề hoặc thiếu skill.

Trước khi tạo run mới sau khi sửa code, cần phiên bản chính sách fingerprint phân biệt byte dữ liệu với code LF chuẩn, liên kết receipt cũ bằng chứng newline; không sửa/bỏ gate cũ. Audit này chưa thay chính sách đầu vào của pipeline.

Audit hiện chỉ kiểm tính toàn vẹn và tổng hợp quyết định đã có, không chỉnh luật từ CV holdout, không xem ranking, không train. Nếu dùng kết quả validation/test để chỉnh phương pháp ở lượt sau, phải ghi nhận exposure và chuẩn bị holdout thích hợp. Giới hạn synthetic và Data Analyst cần JD đủ điều kiện vẫn giữ nguyên.
