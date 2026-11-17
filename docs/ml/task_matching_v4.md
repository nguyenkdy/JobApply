# Đối chiếu nhiệm vụ có bằng chứng v4 — 17/11/2026

**Đã triển khai và chạy `task-evidence-proxy-v4` trên toàn bộ 48,284 cặp (120 CV synthetic / 788 JD) bằng Python chuẩn, không gọi LLM hay dịch vụ mạng.** Chức danh/tên nghề (`role`/`title`) chỉ còn là metadata hiển thị và thống kê phân bố; quyết định gán nhãn kiểm tra bất biến đổi tên chức danh trên cả 48,284 cặp (`title_used_for_decision=false`).

[Receipt từ hai run](reports/20261117-task-matching-v4.json), [policy v4](data_configs/task_evidence_proxy_v4.json), [ví dụ chức danh mới đạt nhãn 2](examples/unseen_title_pair.json), [ví dụ trùng kỹ năng nhưng khác nhiệm vụ](examples/unknown_task_pair.json).

## 1. Quy tắc đối chiếu không phụ thuộc danh sách tên nghề

- **Loại bỏ cổng tên nghề:** Không so khớp chuỗi `cv.role == jd.role`, không dùng danh sách nghề đóng để cho qua hay chặn cặp, và không trích xuất kỹ năng từ tiêu đề công việc (`title_for_matching`).
- **Nhãn 0 (`107` cặp):** Chỉ khi có mâu thuẫn rõ với điều kiện bắt buộc áp dụng được (phủ định kỹ năng bắt buộc hoặc số tháng kinh nghiệm `employment`/`contract` cùng scope thấp hơn ngưỡng bắt buộc). Khác tên nghề, khác nhiệm vụ hoặc thiếu nhắc tới kỹ năng không bị gán `0`.
- **Nhãn 1 (`325` cặp):** Khi cả CV và JD đều có bằng chứng nhiệm vụ cùng họ công việc (`shared_functions`) **và** có công nghệ/kỹ năng chung trích từ nội dung chuyên môn (`shared_skills`), không rơi vào nhánh mâu thuẫn bắt buộc. Có **31 cặp dương tính** trên các JD trước đây chưa xác định được `role`.
- **Nhãn 2 (`0` cặp trong kho hiện tại):** Khi đạt điều kiện nhãn 1, mọi họ nhiệm vụ phát hiện ở JD đều được CV chứng minh, mọi đoạn nhiệm vụ JD đều nằm trong ngữ pháp đóng (`bounded_statement_complete`), toàn bộ phần yêu cầu JD thuộc ngữ pháp kỹ thuật đóng đã được giải thích (`complete_bounded_grammar`), và mọi điều kiện bắt buộc/thời lượng (nếu JD có nêu) đều đạt. **JD không nêu yêu cầu số năm không bị chặn nhãn 2** (đã kiểm chứng trên [unseen_title_pair.json](examples/unseen_title_pair.json)).
- **Trống (`47,852` cặp):** Chưa đủ bằng chứng nhiệm vụ + kỹ năng chung (`46,086` cặp) hoặc giữ nguyên 29 JD ngoài phạm vi phần mềm đã đánh dấu từ dataset trước (`1,766` cặp).

## 2. Kết quả trên 48.284 cặp và so sánh với v3

| Trạng thái | v3 | v4 |
|---|---:|---:|
| Nhãn 0 | 98 | 107 |
| Nhãn 1 | 2,427 | 325 |
| Nhãn 2 | 0 | 0 |
| Chưa nhãn | 45,759 | 47,852 |

| Partition gốc — chỉ chẩn đoán | Cặp | 0 | 1 | 2 | Trống |
|---|---:|---:|---:|---:|---:|
| test (cũ) | 23,640 | 61 | 110 | 0 | 23,469 |
| train (cũ) | 1,004 | 2 | 6 | 0 | 996 |
| validation (cũ) | 23,640 | 44 | 209 | 0 | 23,387 |

| Chuyển trạng thái v3 → v4 | Số cặp |
|---|---:|
| `0->0` | 98 |
| `1->1` | 161 |
| `1->unlabeled` | 2,266 |
| `unlabeled->0` | 9 |
| `unlabeled->1` | 164 |
| `unlabeled->unlabeled` | 45,586 |

Số nhãn `1` giảm từ `2,427` xuống `325` vì v3 cho phép gán nhãn `1` khi trùng tên nghề (`same_specific_occupation`) kèm kỹ năng chung dù chưa bắt được hành động nhiệm vụ trong văn bản; v4 bỏ hẳn điều kiện trùng tên nghề và bắt buộc bằng chứng nhiệm vụ (`action + object`) ở cả hai phía. Ngược lại, v4 mở khóa `164` cặp `unlabeled -> 1` và `9` cặp `unlabeled -> 0` (trong đó có các JD `role` rỗng mà v3 bỏ qua).

## 3. Độ phủ bộ đọc nhiệm vụ và yêu cầu trong v4

- **CV có bằng chứng nhiệm vụ theo mẫu `action + object`:** 13/120 CV (v3: 23/120).
- **JD có bằng chứng nhiệm vụ theo mẫu `action + object`:** 376/788 JD (v3: 361/788).
- **JD có toàn bộ đoạn yêu cầu nằm trọn trong ngữ pháp đóng (`jd_complete_bounded_requirements`):** 0/788 JD.

| Họ nhiệm vụ CV (`functions_cv`) | Số CV |
|---|---:|
| `backend_services` | 6 |
| `infrastructure_operations` | 2 |
| `ml_modeling` | 1 |
| `quality_testing` | 2 |
| `user_interface` | 3 |

| Họ nhiệm vụ JD (`functions_jd`) | Số JD |
|---|---:|
| `backend_services` | 159 |
| `data_analysis` | 52 |
| `data_pipeline` | 100 |
| `database_design` | 45 |
| `infrastructure_operations` | 54 |
| `ml_modeling` | 14 |
| `mobile_application` | 20 |
| `quality_testing` | 71 |
| `user_interface` | 112 |

## 4. Kiểm chứng và lệnh PowerShell

- Hai run `ml_data_runs/20261117_task_matching_v4_01` và `ml_data_runs/20261117_task_matching_v4_02` có **41/41 file giống byte**.
- **210 test đạt**, 21.511 giây (`tests/ml/test_task_matching.py` thêm 22 test mới kiểm tra chức danh chưa từng gặp, đổi tên chức danh bất biến, trùng công nghệ nhưng khác nhiệm vụ, ngữ cảnh phủ định/giả định/tương lai/giảng dạy, ưu tiên cuối câu và bảo toàn offset).
- Toàn bộ 120 CV vẫn giữ `effective_exposure=development`, `evaluation_eligible=false`; chưa huấn luyện model mới.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_task_matching check --artifact '.\ml_data_runs\20261117_task_matching_v4_01'
if ($LASTEXITCODE -ne 0) { throw 'Task matching v4 check failed' }

$v4Out = '.\ml_data_runs\task_matching_v4_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_task_matching prepare --parent .\ml_data_runs\20261117_label_revision_v3_02 --output $v4Out
if ($LASTEXITCODE -ne 0) { throw 'Task matching v4 prepare failed' }

$pairOut = '.\ml_data_runs\pair_inspect_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff') + '.json'
& $pythonML -m ml_task_matching inspect-pair --input .\docs\ml\examples\unseen_title_pair.json --output $pairOut
```
