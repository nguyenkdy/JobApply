# Chuẩn bị mở rộng CV và nhãn — 16/11/2026

**Đã ghép 120 CV synthetic / 12 ngân hàng với toàn bộ 788 JD, tạo và xử lý 48,284 cặp. Chưa đủ điều kiện huấn luyện hoặc đánh giá xếp hạng toàn catalog.** Không chạy model mới; kết quả Bước 4 trên 50 JD vẫn là kết quả lịch sử, không áp dụng cho lô này.

Đọc [receipt sinh từ run](reports/20261116-expanded-preparation.json), [ngân hàng CV mới](../../ml_data_assets/authored_cv_v7/AUTHORING.md), [config CV](data_configs/authored_cv_v7_import.json), [backlog JD theo ID](reports/20261116-jd-evidence-backlog.csv). Báo cáo được sinh bằng `scripts/report-expanded-preparation.py` sau khi kiểm cả bốn run, không suy dữ liệu từ các số tổng hợp cũ.

## Phần đã thực hiện

Viết riêng 90 CV mới thuộc chín ngân hàng và giữ nguyên 30 CV v6. Mỗi hồ sơ mới lưu toàn văn, is_synthetic, source_group, template_group, generation_version, scenario_id, variant_history và câu bằng chứng. Không có renderer ghép câu; `profiles.json` chỉ đóng gói các bản ghi đã viết. Cả 30 CV v6 giữ nguyên ID/namespace, văn bản, metadata, lineage và partition. Chỉ phân bổ nhóm mới, seed 20261116 không thử lại. Không khôi phục lô v5 đã xóa.

Đã kiểm 451 khẳng định kỹ năng, 106 khẳng định thời lượng theo văn bản và offset. Unknown giữ `{}`. Tháng nghề nghiệp, công nghệ, thực tập và dự án không thay thế nhau. Metadata là khẳng định của tác giả synthetic, không phải gold.

| Partition | CV | Nhóm | Ngân hàng |
|---|---:|---:|---|
| train | 60 | 6 | agriculture, commerce, energy, hospitality, nonprofit, public_services |
| validation | 30 | 3 | creative_production, manufacturing, transport |
| test | 30 | 3 | education, research_operations, sports |

Mười nghề đều có 6 CV/train và 3 CV/validation, test: Backend Python, Backend Java, Frontend, DevOps/Cloud, QA/Testing, Backend .NET, Fullstack, Mobile, Data Engineer, AI/ML Engineer. Đây là số thực tế sau chia nhóm, không ép tỷ lệ 60/20/20 bằng cách tách ngân hàng.

| Loại kinh nghiệm | Train | Validation | Test |
|---|---:|---:|---:|
| employment | 12 | 6 | 6 |
| contract | 12 | 6 | 6 |
| internship | 12 | 6 | 6 |
| project | 12 | 6 | 6 |
| unknown | 12 | 6 | 6 |

0 CV nối về development lịch sử, 0 CV bị loại theo kiểm tra khai báo. Đã so 22,320 cặp với 186 CV lịch sử còn giữ; Jaccard từ vựng tối đa 0.034682; giữa ngân hàng 0.073826; 0 câu dài lặp nguyên văn. **Những phép đo này không chứng nhận độc lập ngữ nghĩa.** CV cùng một tác giả AI, đa số là hồ sơ ngắn có cách trình bày tương tự, chưa đại diện CV thật nhiều trang hoặc nguồn tác giả đa dạng. Khác ngân hàng cũng gây khác biệt miền nội dung.

Protocol **known-JD**: tất cả 788 JD / 698 nhóm được dùng chung. JD unknown, generic và ngoài phạm vi vẫn ở catalog; không lén loại để tăng điểm. Giữ exposure parser-development và quan hệ với benchmark cũ; không tuyên bố đánh giá trên JD chưa từng thấy. Không nhập dữ liệu lịch sử vào database app.

## Bộ luật và kết quả nhãn thực tế

Phiên bản `expanded-technical-proxy-v1` dùng luật cố định trên mọi partition, không đọc ranking. Luật cũ vẫn bị chặn khi gặp taxonomy v4; CLI mới xử lý riêng, không sửa nhãn lịch sử.

- **0:** chỉ khi có phủ định kỹ năng rõ ràng trong CV mâu thuẫn với yêu cầu bắt buộc đã phân tích đầy đủ, hoặc thời lượng cùng scope nghề nghiệp thấp hơn ngưỡng bắt buộc rõ ràng.
- **1:** cùng nghề/chức năng có thể chồng lấn và có công nghệ được nêu tích cực ở cả hai phía; còn điều kiện chưa xác định nên chỉ nói tương thích kỹ thuật một phần.
- **2:** cùng nghề, mọi điều kiện kỹ thuật quan sát được đã phân tích và đáp ứng, có ngưỡng thời lượng rõ cùng scope được đáp ứng. Không khẳng định đáp ứng học vấn/ngoại ngữ/tất cả điều kiện tuyển dụng.
- **Trống:** không đủ căn cứ. Khác tên nghề, không nhắc công nghệ, hard candidate, thiếu metadata đều không tự trở thành 0. Ưu tiên không phải bắt buộc; AND/OR, phạm vi điều kiện và câu chưa phân tích được không tự suy diễn.

| Partition | Cặp xử lý | Nhãn 0 | Nhãn 1 | Nhãn 2 | Chưa nhãn |
|---|---:|---:|---:|---:|---:|
| train | 1,004 | 0 | 257 | 0 | 747 |
| validation | 23,640 | 1 | 2100 | 0 | 21539 |
| test | 23,640 | 0 | 1962 | 0 | 21678 |

Tổng có **4,320 cặp mang nhãn proxy (8.95%)**, **43,964 cặp còn trống**. Train lấy 600 random và 404 hard candidates, có 48 lượt thiếu quota; không tạo bù. Validation/test đã tạo đủ lưới CV × 788 JD, nhưng **đủ cặp không có nghĩa đủ nhãn**.

Giới hạn của parser mới là rõ rệt: chỉ 5 JD có câu công nghệ bắt buộc thuộc ngữ pháp đầy đủ đang hỗ trợ, 1 JD có ngưỡng thời lượng đơn giản đủ rõ theo parser này; 428 JD có câu thời lượng chưa phân tích chắc chắn. Có 2293 mệnh đề công nghệ unresolved. Đây **không** có nghĩa chỉ từng đó JD chứa yêu cầu thực tế: bộ đọc ngôn ngữ còn hẹp và dữ liệu có nhiều điều kiện chưa rõ. Metadata thời lượng v4 giữ nguyên; phiên bản nhãn mới không tự coi fallback “professional experience” là bằng chứng scope chính xác.

Train thiếu lớp 0, 2; 120/120 CV chưa có positive nhãn 2 theo luật này. Vì vậy **chưa train LR**, chưa chọn model, chưa tính Recall@5/NDCG@5 toàn catalog và không biến nhãn trống thành 0. Không dùng tỷ lệ kiểm tra schema hợp lệ để tuyên bố nhãn đúng 100%.

## Kiểm chứng và nơi mở dữ liệu

- Intake chính: `ml_data_runs/20261116_authored_cv_v7_01`; lặp: `ml_data_runs/20261116_authored_cv_v7_02` — **99 file giống byte**, gồm manifest.
- Nhãn chính: `ml_data_runs/20261116_expanded_labels_v1_01`; lặp: `ml_data_runs/20261116_expanded_labels_v1_02` — **32 file giống byte**, gồm manifest.
- **110 test đạt**, 69.220 giây; kiểm scope, AND/OR, optional, mâu thuẫn rõ, giữ lineage/partition, lưới census và chặn metric khi nhãn thiếu. Test dùng fixture riêng; không huấn luyện catalog thực.
- Xác minh 3 CSV nguồn + 51 file pilot và 6 run lịch sử theo receipt trước đó không đổi. Tám thư mục v5 vẫn không tồn tại. Không commit dữ liệu nguồn lớn, không đổi API/UI/Docker/VM, chưa commit/push.

Trong intake: `authored/cvs.csv` là 90 CV mới; `prior/cvs.csv` là 30 CV giữ nguyên; `records.jsonl` ghép 908 record; `assignments.jsonl`, `distributions.json`, `leakage_report.json` cho biết split thực tế. `cv_import_config.json` và snapshot giữ namespace riêng của từng nguồn.

Trong run nhãn: `labels.csv` để lọc theo partition/trạng thái; `evidence.jsonl` ghi quyết định từng cặp; `cv_facts.json` và `jd_facts.json` lưu câu trích/offset, scope, toán tử và các phần chưa phân tích. `policy.json`, `parsing_coverage.json`, `summary.json`, `manifest.json` ghi luật, độ phủ, hash. Không có model mới trong các thư mục này.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_data check-cv-intake --artifact '.\ml_data_runs\20261116_authored_cv_v7_01'
if ($LASTEXITCODE -ne 0) { throw 'CV intake check failed' }
& $pythonML -m ml_data check-expanded-labels --intake '.\ml_data_runs\20261116_authored_cv_v7_01' --artifact '.\ml_data_runs\20261116_expanded_labels_v1_01'
if ($LASTEXITCODE -ne 0) { throw 'Proxy label check failed' }

Import-Csv '.\ml_data_runs\20261116_expanded_labels_v1_01\labels.csv' | Group-Object partition,label_status,relevance_0_1_2 | Select-Object Count,Name

$runStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$cvOut = '.\ml_data_runs\cv_expanded_' + $runStamp
$labelOut = '.\ml_data_runs\labels_expanded_' + $runStamp
& $pythonML -m ml_data prepare-cv-intake --metadata-run .\ml_data_runs\20261116_jd_metadata_v4_03 --catalogue-run .\ml_data_runs\20261116_jd_catalogue_v1_01 --preparation-run .\ml_data_runs\20261114_pretraining_v3_01 --assets .\ml_data_assets\authored_cv_v7 --prior-intake .\ml_data_runs\20261116_authored_cv_v6_02 --output $cvOut
if ($LASTEXITCODE -ne 0) { throw 'Expanded CV import failed' }
& $pythonML -m ml_data prepare-expanded-labels --intake $cvOut --output $labelOut
if ($LASTEXITCODE -ne 0) { throw 'Expanded labeling failed' }
```

## Điều kiện còn thiếu trước huấn luyện — chưa thực hiện

1. Mở rộng parser điều kiện trên **JD đã thuộc development** bằng fixture riêng: câu thời lượng có scope nghề/công nghệ, danh sách AND/OR, điều kiện nhiều cấp độ, phủ định và ưu tiên. Cần báo cả phần không hiểu; không thay “không rõ” bằng “không đạt”. Backlog ID phía trên cho biết mệnh đề nào đang thiếu khả năng phân tích; câu gốc ở run local. Phiên bản hiện tại chỉ là chính sách proxy bảo thủ có test, chưa hoàn thành độ phủ nhãn cần cho thí nghiệm.
2. Bổ sung bằng chứng cho các quyết định tương thích/không tương thích còn thiếu, kiểm đủ lớp ở train và positive ở từng nhóm đánh giá. Không sửa CV để khớp JD đích hoặc tự nâng nhãn. Nếu sửa luật/features dựa vào kết quả của nhóm validation/test hiện tại, nhóm đó phải chuyển development; không đổi seed/lineage để gọi lại là test mới.
3. Chỉ huấn luyện sau khi khóa phiên bản dữ liệu, luật và phạm vi đánh giá. Nếu chọn đánh giá trên tập con có nhãn, phải công bố phạm vi và thiên lệch chọn mẫu; không gọi đó là Recall/NDCG trên toàn 788 JD. Nhãn do luật tạo vẫn chỉ đo khả năng học/đồng thuận với luật, chưa xác nhận phù hợp tuyển dụng thật.
4. Data Analyst vẫn là mục tiêu: kho hiện tại chưa bổ sung được JD mới đủ điều kiện ngoài development cho positive benchmark. Cần JD có nhiệm vụ phân tích, điều kiện và provenance rõ; không thay Data Analyst bằng Data Engineer để báo đủ nghề. Muốn kết luận trên ứng viên thật còn cần nguồn CV được phép sử dụng và bằng chứng đánh giá ngoài bộ luật, không bắt buộc vòng hai reviewer.

Không tăng số CV đơn thuần để che thiếu nhãn. Lượt này hoàn thành công cụ tiếp nhận, chia nhóm, xử lý cặp, kiểm chứng và báo cáo; **điều kiện sẵn sàng huấn luyện vẫn chưa đạt**, được lưu rõ thay vì tuyên bố hoàn tất giả.
