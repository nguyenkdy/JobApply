# Dọn thành phần CV v2 cũ — 14/11/2026

60 CV cũ không hỏng nội dung. Lỗi là chia lại template nhưng bỏ quan hệ họ gốc, khiến split cũ không độc lập. Chúng đã được giữ development và không tham gia train/validation/test của lô 60 CV mới.

## Đã xóa khỏi cây nguồn hiện hành

- `ml_data_assets/synthetic_cv_v2/design.json` và `scenarios.json`, cùng thư mục rỗng. Hai file khớp SHA256 với snapshot trong `20261114_benchmark_audit_02/cv_batch` trước khi xóa.
- `ml_data/benchmark_prep.py`: bỏ luồng dựng lại benchmark v2, kiểm toán chuyển template và cổng readiness cũ. Hàm kiểm tra JD bất biến vẫn dùng được tách sang `ml_data/jd_integrity.py`.
- Hai lệnh CLI `prepare-benchmark` và `training-readiness`.
- `scripts/report-benchmark-audit.py` và config `docs/ml/data_configs/benchmark_v2_import.json` dành riêng cho lô cũ.
- Hàm `comparable_experience` không còn được labeler gọi. Test giờ kiểm trực tiếp `experience_coverage` đang sử dụng.

Test lỗi đổi template dùng sáu hồ sơ fixture nhỏ, nối hai họ gốc qua ba họ mới; không còn phụ thuộc 60 CV v2. Test chuẩn bị dữ liệu dùng renderer v1 còn được hỗ trợ để tạo fixture development, không dựng lại benchmark thật. Không xóa kiểm tra chống leakage, bảo toàn nguồn hay unknown.

## Giữ lại vì đang được sử dụng

- `20261114_benchmark_audit_02`: nguồn CV cũ đã sửa ancestry mà `prepare-experiment --audited-run` đọc, chỉ nhập ở development.
- `20261113_cv_expansion_v1/synthetic_cvs`: tham chiếu CV v1 để phát hiện cùng nguồn/trùng/gần trùng.
- `20261113_benchmark_v2/run_08`: nguồn catalog 50 JD cố định và provenance lịch sử.
- Hai run `20261114_pretraining_v3_01` và `_02`: snapshot niêm phong gồm dataset, ancestry, bằng chứng và 3.000 cặp nhãn mới. Xóa riêng CV cũ bên trong sẽ làm sai manifest.
- Assets/renderer v1, importer, grouping và các test còn dùng cho hồi quy lịch sử. Báo cáo kiểm toán, config trỏ tới snapshot có ancestry và lịch sử nhãn được giữ để giải thích nguồn gốc.

Vì vậy **chưa xóa sạch mọi bản của 60 CV cũ**. Xóa sạch sẽ ảnh hưởng tái tạo và đối chiếu chống leakage. Dọn lượt này chỉ gỡ đầu vào tạo CV v2 cùng các lệnh không cần dùng tiếp; không thay đổi dữ liệu/split/nhãn mới. Không chạy Bước 4.

[Receipt đường dẫn, kích thước và checksum đã xóa](reports/20261114-retired-cv-cleanup.json). Các snapshot đầy đủ vẫn nằm trong `ml_data_runs/` đã Git ignore. Không commit/push hoặc thay đổi API/UI/Docker/VM.

Kiểm tra sau dọn: **64/64 test đạt**, Ruff đạt, 22/22 điều kiện của run v3 đạt. Manifest bốn run đầu vào và hai run v3 vẫn hợp lệ; ba CSV nguồn và 51 file pilot không đổi. Dữ liệu mới vẫn 60 CV / 12 họ, split 30/15/15 và 3.000 cặp nhãn. Không cần sinh lại nhãn hoặc đổi split.

```powershell
Set-Location D:\JobApply
python -m ml_data check-pretraining --artifact .\ml_data_runs\20261114_pretraining_v3_01
if ($LASTEXITCODE -ne 0) { throw 'Pretraining checks failed' }
```

Lệnh tái tạo hiện hành trong [bàn giao](pretraining_handoff.md) vẫn dùng snapshot đầu vào đã giữ, không cần assets v2 đã xóa. Run cũ giữ nguyên code snapshot; run tương lai sẽ có hash mã nguồn khác do dọn code, không được tuyên bố toàn bộ manifest giống lượt trước.
