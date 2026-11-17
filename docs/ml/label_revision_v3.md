# Parser và nhãn kỹ thuật v3 — development

Đã xử lý 48,284 cặp của 120 CV synthetic và 788 JD: **98 nhãn 0, 2,427 nhãn 1, 0 nhãn 2, 45,759 cặp chưa nhãn**. Chưa train. Số nhãn và độ phủ không chứng minh độ chính xác ngữ nghĩa.

V3 thêm các mẫu thời lượng khớp toàn câu, prefix kỹ năng và ưu tiên cuối câu có phạm vi rõ. Tách câu có kiểm tra offset; phần còn chưa hiểu giữ unresolved. Không gán thời gian từng công nghệ từ tổng kinh nghiệm. Các phủ định, điều kiện, lựa chọn và scope mơ hồ vẫn bị chặn. Bằng chứng và thay đổi từng mệnh đề nằm trong `clause_changes.jsonl`; bản gốc và nhãn v2 không bị sửa.

Parser có điều kiện công nghệ bắt buộc đọc được ở **31 JD**, thời lượng có scope ở **88 JD**. Các lý do chưa hiểu nằm trong `summary.json`; phần chuẩn hóa này chưa giải quyết toàn bộ nội dung tự nhiên.

| Partition gốc, chỉ chẩn đoán | Cặp | 0 | 1 | 2 | Trống |
|---|---:|---:|---:|---:|---:|
| train (cũ) | 1004 | 2 | 181 | 0 | 821 |
| validation (cũ) | 23640 | 41 | 1180 | 0 | 22419 |
| test (cũ) | 23640 | 55 | 1066 | 0 | 22519 |

## Nguyên nhân ô trống theo luật hiện tại — loại trừ nhau

- `no_exact_shared_skill`: 1,129
- `no_jd_core_skill`: 66
- `occupation_transfer_without_task_evidence`: 37,120
- `outside_software_scope`: 1,766
- `unresolved_occupation_and_tasks`: 5,678

Đây là lý do thuật toán dừng, không chứng nhận sự thật rằng CV/JD không liên quan. `label_one_gaps_overlapping` trong summary chỉ ra các điều kiện còn thiếu để nhãn 1 lên nhãn 2; các cờ có thể trùng nhau.

## Điều kiện trước huấn luyện

Cả 120 CV / 12 ngân hàng tiếp tục là development. Giữ nguyên lineage, seed và partition; không có test độc lập cho v3. Cần tiếp tục xử lý mẫu câu chưa hiểu và thông tin thiếu bằng bằng chứng; không viết lại CV để khớp JD. Khóa phương pháp trước khi tiếp nhận nhóm đánh giá mới. Không tự gọi nhãn là gold, không tạo điểm Recall/NDCG trên ô trống. Data Analyst vẫn là mục tiêu, cần JD đủ điều kiện riêng, không thay bằng Data Engineer.

## So với v2 và kiểm chứng

| Trạng thái | v2 | v3 |
|---|---:|---:|
| Nhãn 0 | 41 | 98 |
| Nhãn 1 | 2,434 | 2,427 |
| Nhãn 2 | 0 | 0 |
| Chưa nhãn | 45,809 | 45,759 |

Hai run `ml_data_runs/20261117_label_revision_v3_02` và `ml_data_runs/20261117_label_revision_v3_03` có **44/44 file giống byte**. Checker xác minh nguồn v2, dựng lại facts/nhãn/bằng chứng, tổng hợp và báo cáo; kiểm offset về câu gốc. **158 test đạt**, 28.269 giây. Nguồn CSV, pilot, CV, lineage, partition và nhãn v2 giữ nguyên; 50 file bảo vệ khớp byte, bốn mã/lock chỉ chấp nhận khác CRLF/LF đã chứng minh từ trước. Không đổi API/UI/Docker/VM.

Run `20261117_label_revision_v3_01` là snapshot trung gian trước bổ sung chốt chặn câu thay thế/phủ định và bỏ scope suy đoán từ “development experience”; giữ nguyên để truy vết, không dùng làm bản hiện hành.

[Receipt sinh từ run](reports/20261117-label-revision-v3.json), [policy](data_configs/technical_proxy_v3.json), [bàn giao v2](label_revision_v2.md).

Giải thích các nhóm ô trống, mỗi cặp chỉ thuộc một dòng theo thứ tự dừng của luật:

| Lý do chưa kết luận | Cặp |
|---|---:|
| Chưa có kỹ năng chung theo bằng chứng đã đọc | 1,129 |
| Chưa có bằng chứng kỹ năng cốt lõi của JD | 66 |
| Khác nghề, chưa có bằng chứng nhiệm vụ chung | 37,120 |
| Ngoài phạm vi benchmark phần mềm | 1,766 |
| Chưa xác định được nghề và nhiệm vụ JD | 5,678 |

Các điều kiện ngăn nhãn 2 dưới đây có thể chồng lấn, không cộng thành tổng:

- Chưa đối chiếu được thời lượng cùng scope: 277 cặp nhãn 1.
- CV chưa đủ bằng chứng cho kỹ năng bắt buộc: 105 cặp nhãn 1.
- Chưa đọc được điều kiện công nghệ bắt buộc: 2,293 cặp nhãn 1.
- Chưa đọc được thời lượng có scope: 2,128 cặp nhãn 1.
- Chưa cùng nghề cụ thể: 246 cặp nhãn 1.
- Còn yêu cầu chưa đọc hết hoặc khoảng thời gian chưa rõ: 2,355 cặp nhãn 1.

## Mã và cách kiểm lại

- `ml_data/policies/technical_v3.py`: phần mở rộng cú pháp, dùng nguyên quy tắc quyết định v2.
- `ml_data/policies/__main__.py`: tạo/check run v3, manifest và chẩn đoán.
- `tests/ml/test_policy_v3.py`: fixture ngữ pháp và schema canonical, giữ nhãn/partition/exposure đúng hợp đồng.
- `scripts/report-label-revision-v3.py`: sinh tài liệu và receipt sau khi kiểm hai run.

Không sửa module v2 đã đóng băng. Package con được snapshot riêng ở `policy_source/` và đưa vào manifest/fingerprint v3; mã cũ vẫn ở `tool_source/`.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_data.policies check --artifact '.\ml_data_runs\20261117_label_revision_v3_02'
if ($LASTEXITCODE -ne 0) { throw 'V3 check failed' }

$v3Out = '.\ml_data_runs\label_revision_v3_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_data.policies prepare --parent .\ml_data_runs\20261117_label_revision_v2_02 --output $v3Out
if ($LASTEXITCODE -ne 0) { throw 'V3 preparation failed' }
```

Đây là kết quả đã thực hiện của lượt v3. Chưa tạo CV mới, chưa khóa phương pháp cuối cùng, chưa xây holdout mới hoặc huấn luyện. Việc tiếp theo là xử lý các nhóm câu chưa hiểu theo `clause_changes.jsonl`/`jd_facts.json` và các khoảng trống bằng chứng CV, không đổi ô trống thành 0. Nhãn tổng hợp từ quy tắc vẫn chỉ là proxy; chưa chứng minh chất lượng trên ứng viên thật.
