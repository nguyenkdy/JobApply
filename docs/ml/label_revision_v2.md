# Quy tắc kỹ thuật v2 và chấm lại development — 17/11/2026

**Đã triển khai phiên bản kiểm tra đầu vào và bộ luật mới, chạy đủ 48,284 cặp hai lần, chưa train.** Lô vẫn là 120 CV synthetic và 788 JD. Kết quả thực tế: **41 nhãn 0, 2,434 nhãn 1, 0 nhãn 2, 45,809 cặp chưa nhãn**. Đây chưa phải dataset sẵn sàng cho thí nghiệm xếp hạng ba mức.

[Receipt sinh từ run](reports/20261117-label-revision-v2.json), [định nghĩa chính sách](data_configs/technical_proxy_v2.json), [audit dẫn đến thay đổi này](readiness_audit.md).

## Giữ dữ liệu và sửa kiểm tra đầu vào

`protected-input-contract-v2` giữ hash lịch sử và liên kết tới manifest audit. 50 file vẫn phải khớp nguyên byte; chỉ 4 đường dẫn mã/lock có chứng cứ CRLF/LF được chấp nhận theo nội dung LF chuẩn đã kiểm. Thay mã, đổi dependency hoặc đổi newline CSV vẫn bị từ chối. Không ghi đè receipt cũ, không sửa gate strict của lệnh v1.

Mã thực thi v2 lưu cả hash raw và hash LF, cùng snapshot `tool_source/`. Checker so snapshot với fingerprint đã khai và nội dung LF của code hiện tại; khác nội dung thực thi bị chặn. Python/platform/Unicode được ghi trong `runtime.json`; pipeline này chỉ dùng thư viện chuẩn, không tải/chạy encoder.

CV/JD, lineage, ID, partition, seed, file nguồn và nhãn v1 giữ nguyên. V2 tạo facts/nhãn ở artifact riêng, liên kết manifest các đầu vào. Không nhập JD vào database app, không đổi API/UI/Docker/VM.

## Luật đã thay đổi những gì?

- Đọc nhiều cách viết yêu cầu tiếng Việt/Anh; phân biệt phần ưu tiên, yêu cầu trộn ưu tiên và điều kiện theo cấp độ. Phần không đọc hết vẫn unresolved.
- Có cây AND/OR giữ ngoặc: `(Python hoặc Java) và SQL` khác `Python hoặc Java và SQL`. Danh sách dấu phẩy/slash đơn thuần vẫn chưa được tự coi là AND/OR.
- Chuẩn hóa alias cụ thể như Postgres/PostgreSQL, ReactJS/React; vẫn tách Java/JavaScript, React/React Native, .NET/ASP.NET Core.
- Đọc ngưỡng tháng/năm, dấu cộng và số thập phân, giữ scope nghề/công nghệ. Khoảng năm giữ cận trên chưa rõ cách diễn giải, không dùng để khẳng định nhãn 2. Tổng kinh nghiệm không biến thành thời gian từng công nghệ; dự án/thực tập không thay thời gian nghề nghiệp.
- Cùng nghề cụ thể và có công nghệ chung vẫn có thể nhận nhãn 1. Khi khác nghề, cần **bằng chứng nhiệm vụ chung trong văn bản** cùng kỹ năng chung; không chỉ dùng một nhóm nghề rộng. Có 247 nhãn 1 được hỗ trợ theo nhánh nhiệm vụ chung này. Không suy không phù hợp chỉ từ khác chức danh hoặc thiếu skill trong CV.
- Nhãn 0 chỉ dựa trên mâu thuẫn điều kiện bắt buộc rõ ràng. Trong run thực, 41 nhãn 0 đến từ thời lượng cùng scope không đạt; 0 đến từ phủ định công nghệ. “Chưa quản trị Kubernetes” không bị đổi thành “chưa từng dùng Kubernetes”.

Luật v2 vẫn là **proxy kỹ thuật**, không chứng nhận phù hợp tuyển dụng, chưa đánh giá đầy đủ học vấn/ngoại ngữ/kỹ năng mềm. Cây logic có test không có nghĩa đã hiểu hết văn bản tự nhiên.

## Độ phủ parser thực tế

| Chỉ số JD | v1 | v2 |
|---|---:|---:|
| Có mệnh đề công nghệ bắt buộc đọc được đầy đủ | 5 | 24 |
| Có thời lượng và scope được parser chấp nhận | 1 | 31 |

Overlay nghề thay đổi 14 JD theo cụm chức danh rõ, số JD role rỗng còn 122. Có 30 nghề còn generic, 29 JD ngoài phạm vi phần mềm theo v2 (vẫn giữ trong catalog). Một chức danh Curriculum Developer được nhận diện là Education/Training; không đổi dữ liệu nguồn để loại khỏi kho.

Phát hiện bằng chứng nhiệm vụ theo ngữ pháp hiện tại ở 361/788 JD và 23/120 CV. Số còn lại không có nghĩa không có nhiệm vụ: cách đọc vẫn hẹp và CV synthetic có cách diễn đạt ngắn, tương tự nhau. Còn 4,014 mệnh đề unresolved trong phạm vi câu v2 xem xét; phạm vi này rộng hơn v1 nên không so hai số unresolved như cùng một mẫu.

## Nhãn thay đổi ra sao?

| Nhóm partition gốc — chỉ để chẩn đoán | Số cặp | Nhãn 0 | Nhãn 1 | Nhãn 2 | Trống |
|---|---:|---:|---:|---:|---:|
| train (cũ) | 1,004 | 1 | 181 | 0 | 822 |
| validation (cũ) | 23,640 | 14 | 1185 | 0 | 22441 |
| test (cũ) | 23,640 | 26 | 1068 | 0 | 22546 |

| Chuyển nhãn v1 → v2 | Số cặp |
|---|---:|
| `0->0` | 1 |
| `1->0` | 6 |
| `1->1` | 2,207 |
| `1->unlabeled` | 2,106 |
| `unlabeled->0` | 34 |
| `unlabeled->1` | 227 |
| `unlabeled->unlabeled` | 43,703 |

Số nhãn giảm so với v1 chủ yếu vì luật v1 cho phép các nghề thuộc một nhóm rộng nhận nhãn 1 khi trùng công nghệ; v2 yêu cầu bằng chứng nhiệm vụ nếu nghề khác nhau. **Không gọi việc giảm/tăng nhãn là tăng độ chính xác.** Không có đánh giá độc lập chứng minh nhãn v2 đúng hơn. Việc mở rộng parser và siết tiền đề tương thích là hai thay đổi khác nhau.

## Exposure: không còn gọi validation/test cũ là holdout độc lập

Lần sửa chính sách này bắt nguồn từ audit của toàn bộ lô, có cả validation/test. Vì vậy `exposure_overlay.json` đánh dấu **cả 120 CV / 12 nhóm là development**, `evaluation_eligible=false`, không có CV test độc lập còn lại cho chính sách mới.

Không đổi hoặc xóa partition gốc: `source_assignments.jsonl` giống byte file intake, cột `partition` trong nhãn chỉ giữ tên nhóm cũ để đối chiếu. **Không dùng tên cột đó để coi các cặp là holdout mới.** Mọi dòng có `effective_exposure=development`; artifact có loại `development-label-revision`, không phải đầu vào pretraining-ready. Không đổi seed, bẻ nhóm hoặc sửa lineage để tạo độc lập giả.

## Kiểm chứng và nơi xem

- Run chính `ml_data_runs/20261117_label_revision_v2_02`; lặp `ml_data_runs/20261117_label_revision_v2_03`: **39/39 file giống byte**.
- **142 test đạt**, 30.444 giây. Test mới bao gồm scope, range, logic ngoặc, ưu tiên/điều kiện, task evidence, phủ định, checksum và exposure cả nhóm. Các test dùng fixture riêng.
- Checker tái dựng facts từ input, kiểm offset, áp lại policy cho toàn bộ cặp, đối chiếu CSV/evidence/tổng hợp/lineage/partition/exposure. Input contract kiểm nguồn và chứng cứ newline.
- `labels.csv`, `evidence.jsonl`: quyết định từng cặp và căn cứ; `cv_facts.json`, `jd_facts.json`: phần trích xuất; `summary.json`: phân bố và thay đổi so với v1.
- `input_contract.json`, `input_receipt.json`, `execution_fingerprints.json`, `runtime.json`, `manifest.json`: provenance, môi trường và kiểm toàn vẹn.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_data check-label-revision --artifact '.\ml_data_runs\20261117_label_revision_v2_02'
if ($LASTEXITCODE -ne 0) { throw 'Label revision check failed' }

$revisionOut = '.\ml_data_runs\label_revision_v2_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_data prepare-label-revision --intake .\ml_data_runs\20261116_authored_cv_v7_01 --old-labels .\ml_data_runs\20261116_expanded_labels_v1_01 --audit .\ml_data_runs\20261116_readiness_audit_v1_01 --output $revisionOut
if ($LASTEXITCODE -ne 0) { throw 'Label revision failed' }
```

## Điều kiện còn thiếu — chưa huấn luyện

Nhóm train gốc chỉ có 1 nhãn 0, 181 nhãn 1 và 0 nhãn 2. Hai lớp cho phép một số thuật toán chạy về mặt kỹ thuật, nhưng dữ liệu này **chưa đáp ứng mục tiêu thí nghiệm relevance 0/1/2** và không còn holdout độc lập. Không train, không chọn model, không đo Recall@5/NDCG@5 từ các ô trống.

Tiếp theo cần kiểm chứng ngữ nghĩa và mở rộng các cấu trúc yêu cầu còn chưa hiểu trên development; hoàn thiện bằng chứng theo scope của CV mà không viết CV để khớp JD đích. Sau khi khóa phương pháp, mới chuẩn bị nhóm CV đánh giá mới có nguồn/lineage độc lập phù hợp. Không tăng số CV để che thiếu nhãn hoặc tự gọi nhãn do luật tạo là gold. Data Analyst vẫn cần JD đủ điều kiện cho benchmark; không bị thay bằng Data Engineer.
