# Mở rộng ngữ pháp nhiệm vụ & yêu cầu có bằng chứng v5 — 17/11/2026

**Đã triển khai và chạy `task-evidence-proxy-v5` (`ml_task_matching_v5`) trên toàn bộ 48,284 cặp (120 CV synthetic / 788 JD) bằng Python chuẩn, không gọi LLM hay dịch vụ mạng.** Chức danh/tên nghề (`role`/`title`) chỉ là metadata hiển thị và thống kê phân bố; quyết định gán nhãn kiểm tra bất biến đổi tên chức danh trên cả 48,284 cặp (`title_used_for_decision=false`).

[Receipt từ hai run](reports/20261117-task-matching-v5.json), [policy v5](data_configs/task_evidence_proxy_v5.json), [báo cáo v4 tiền nhiệm](task_matching_v4.md), [ví dụ chức danh mới đạt nhãn 2](examples/unseen_title_pair.json), [ví dụ trùng kỹ năng nhưng khác nhiệm vụ](examples/unknown_task_pair.json).

## 1. Các cải tiến ngữ pháp đóng từ v4 lên v5

1. **Lọc phủ định và tương lai ở cấp mệnh đề (`clause-local negation/future`) thay vì loại bỏ cả câu:**
   - Trong `v4`, bất kỳ câu nào chứa từ `chưa` hoặc `không` (kể cả trong mệnh đề phụ mô tả trạng thái dữ liệu như `"SQLite giữ lần ghi chưa đồng bộ"`, `"những dòng chưa hợp lệ"`, `"đã được ghi nhận hay chưa"`) đều bị loại bỏ toàn bộ nhiệm vụ và kỹ năng.
   - Trong `v5`, phủ định và tương lai được kiểm tra cục bộ trong mệnh đề điều khiển hành động hoặc kỹ năng (`CLAUSE_BOUNDARY`, `BRIDGE_BOUNDARY`), giúp khôi phục **39/120 CV** bị rơi kỹ năng trong `v4` (`0/120` CV mất kỹ năng trong `v5`) đồng thời giữ nguyên tất cả rào chắn phủ định/giả định/tương lai/giảng dạy.
2. **Mở rộng ngữ pháp nhiệm vụ `action + object` và `carrier + action + object` (`120/120` CV, `489/788` JD):**
   - Bổ sung mẫu chủ ngữ công nghệ/framework đứng trước động từ và tân ngữ nghiệp vụ trong cùng mệnh đề (ví dụ: `"C#, ASP.NET Core và SQL Server lưu khoảng ngày"`, `"React, TypeScript và CSS hiển thị sức chứa"`, `"Flutter, Dart và SQLite lưu số hiệp"`, `"Postman thử hủy lịch"`, `"Linux, Ansible và Docker quản lý máy giả lập"`).
   - Độ phủ nhiệm vụ CV tăng từ **13/120 (`10.8%`)** ở `v4` lên **120/120 (`100.0%`)** ở `v5`, phủ đủ cả **10/10 nhóm vai trò CV** (12/12 CV mỗi vai trò) mà hoàn toàn không đọc `cv.role`.
   - Độ phủ nhiệm vụ JD tăng từ **376/788 (`47.7%`)** ở `v4` lên **489/788 (`62.1%`)** ở `v5`.
3. **Trích xuất phủ định công nghệ tường minh cấp mệnh đề (`30/120` CV):**
   - Mở rộng bộ đọc `nonuse` để bắt các mệnh đề phủ định công nghệ được tác giả cài trong CV nhưng đứng sau dấu phẩy/chấm phẩy hoặc đi kèm mệnh đề phụ (`"chưa sử dụng Kafka"`, `"chưa dùng Terraform"`, `"chưa sử dụng Kubernetes"`, `"chưa dùng Spark"`, `"chưa sử dụng Selenium"`, `"chưa có kinh nghiệm iOS"`, `"không có bằng chứng làm Android"`), nâng số CV có bằng chứng `nonuse` từ `8/120` lên `30/120` với offset trích dẫn nguyên văn.
4. **Mở rộng ngữ pháp yêu cầu kỹ thuật, thời lượng và phạm vi phi kỹ thuật (`33/788` JD đạt `complete_bounded_grammar`):**
   - Sửa lỗi tách nhầm số thứ tự đầu dòng (`1.`, `2.`, `3.`) thành câu độc lập.
   - Bổ sung phân tích biểu thức công nghệ có ngoặc đơn (`.NET (C#)`), danh sách lựa chọn tường minh (`một trong các Web framework phổ biến: Django, Ruby on Rails, Node.js, PHP`), và các biến thể thời lượng có phạm vi rõ ràng.
   - Ghi nhận tường minh các dòng yêu cầu phi công nghệ thuộc phạm vi đã khai báo (bằng cấp đại học, ngoại ngữ Anh/Nhật/Trung, kỹ năng mềm làm việc nhóm/giao tiếp, thủ tục nộp CV) vào trạng thái `outside_technical_scope` thay vì đánh đồng với yêu cầu kỹ thuật chưa giải thích được (`unresolved`). Các yêu cầu công nghệ lạ (như `Must know SecretFramework`) vẫn giữ trạng thái `unresolved` và chặn nhãn `2`.

## 2. Kết quả trên 48.284 cặp và so sánh với v4

| Trạng thái | v4 | v5 |
|---|---:|---:|
| Nhãn 0 | 107 | 290 |
| Nhãn 1 | 325 | 4,227 |
| Nhãn 2 | 0 | 3 |
| Chưa nhãn | 47,852 | 43,764 |

| Partition gốc — chỉ chẩn đoán | Cặp | 0 | 1 | 2 | Trống |
|---|---:|---:|---:|---:|---:|
| test (cũ) | 23,640 | 166 | 1,941 | 0 | 21,533 |
| train (cũ) | 1,004 | 9 | 201 | 0 | 794 |
| validation (cũ) | 23,640 | 115 | 2,085 | 3 | 21,437 |

| Chuyển trạng thái v4 → v5 | Số cặp |
|---|---:|
| `0->0` | 107 |
| `1->0` | 3 |
| `1->1` | 238 |
| `1->unlabeled` | 84 |
| `unlabeled->0` | 180 |
| `unlabeled->1` | 3,989 |
| `unlabeled->2` | 3 |
| `unlabeled->unlabeled` | 43,680 |

- **Nhãn 0 (`290` cặp, tăng từ `107` ở v4):** Toàn bộ `107` cặp nhãn `0` của `v4` được giữ nguyên (`0->0: 107`), đồng thời phát hiện thêm `183` cặp mâu thuẫn bắt buộc mới (`unlabeled->0: 180`, `1->0: 3`) nhờ mở rộng mệnh đề thời lượng/bắt buộc trên JD và bắt đủ 30/120 CV có khai báo `nonuse`.
- **Nhãn 1 (`4,227` cặp, tăng từ `325` ở v4):** Tăng **13,0 lần** khi cả 10/10 nhóm CV đều có bằng chứng nhiệm vụ và khôi phục đầy đủ kỹ năng bị lọc nhầm ở `v4`. Có **395 cặp dương tính** (`1` hoặc `2`) trên các JD không có `role` xác định.
- **Nhãn 2 (`3` cặp trong kho hiện tại, tăng từ `0` ở v4):** Các cặp đạt đồng thời mọi họ nhiệm vụ JD, mọi đoạn nhiệm vụ JD thuộc ngữ pháp đóng, toàn bộ đoạn yêu cầu JD thuộc ngữ pháp đóng (`33/788` JD), và thỏa mãn mọi điều kiện công nghệ bắt buộc cùng số tháng kinh nghiệm `employment`/`contract` cùng scope.

## 3. Độ phủ bộ đọc nhiệm vụ và yêu cầu trong v5

- **CV có bằng chứng nhiệm vụ (`action + object` / `carrier + action + object`):** 120/120 CV (v4: 13/120).
- **JD có bằng chứng nhiệm vụ:** 489/788 JD (v4: 376/788).
- **JD có toàn bộ đoạn yêu cầu nằm trọn trong ngữ pháp đóng (`jd_complete_bounded_requirements`):** 33/788 JD (v4: 0/788).

| Họ nhiệm vụ CV (`functions_cv`) | Số CV |
|---|---:|
| `backend_services` | 48 |
| `data_pipeline` | 12 |
| `infrastructure_operations` | 12 |
| `ml_modeling` | 12 |
| `mobile_application` | 12 |
| `quality_testing` | 12 |
| `user_interface` | 24 |

| Họ nhiệm vụ JD (`functions_jd`) | Số JD |
|---|---:|
| `backend_services` | 260 |
| `data_analysis` | 56 |
| `data_pipeline` | 52 |
| `database_design` | 52 |
| `infrastructure_operations` | 88 |
| `ml_modeling` | 48 |
| `mobile_application` | 40 |
| `quality_testing` | 99 |
| `user_interface` | 144 |

## 4. Kiểm chứng và lệnh PowerShell

- Hai run `ml_data_runs/20261117_task_matching_v5_01` và `ml_data_runs/20261117_task_matching_v5_02` có **41/41 file giống byte**.
- **237 test đạt**, 35.752 giây (`tests/ml/test_task_matching_v5.py` thêm 27 test mới kiểm tra toàn bộ bất biến v4/v5, phủ định cục bộ cấp mệnh đề, mẫu `carrier + action + object`, phủ định công nghệ tường minh `nonuse`, cây yêu cầu có ngoặc/lựa chọn `một trong`, và đối chiếu byte-identical hai bản đóng dấu v5).
- Toàn bộ 120 CV vẫn giữ `effective_exposure=development`, `evaluation_eligible=false`; chưa huấn luyện model mới.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_task_matching_v5 check --artifact '.\ml_data_runs\20261117_task_matching_v5_01'
if ($LASTEXITCODE -ne 0) { throw 'Task matching v5 check failed' }

$v5Out = '.\ml_data_runs\task_matching_v5_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_task_matching_v5 prepare --parent .\ml_data_runs\20261117_task_matching_v4_01 --output $v5Out
if ($LASTEXITCODE -ne 0) { throw 'Task matching v5 prepare failed' }

$pairOut = '.\ml_data_runs\pair_inspect_v5_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff') + '.json'
& $pythonML -m ml_task_matching_v5 inspect-pair --input .\docs\ml\examples\unseen_title_pair.json --output $pairOut
```
