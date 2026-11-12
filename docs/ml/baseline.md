# Mốc 0 — Baseline có thể tái tạo

Ngày 12/11/2026, nhánh `docs/ml-readme-handoff-20261112`. Phạm vi là **development/regression trên nhãn AI**. Không có nhãn gold mới, không chốt model, không triển khai recommendation hay thay đổi dữ liệu VM.

## Hiện trạng xác minh trước khi sửa

- Đã đọc README và đối chiếu code/config của pilot, experience v2, Account/Job/Application, runtime, frontend, triển khai và tests. Mọi file Git theo dõi có byte hash trong `repository_inventory.json` của run; CSV được đọc theo record, không đếm dòng vật lý của văn bản nhiều dòng. Artifact joblib cũ chỉ kiểm tra byte/hash, không unpickle.
- Có 50 JD, 6 CV giả lập và 300 cặp đầy đủ. Nhãn AI: 211 nhãn 0, 71 nhãn 1, 18 nhãn 2. Cột thứ tư mất tên và cả 300 ô trống. Template và code tạo template dùng `reviewer`; đây là căn cứ dựng schema dẫn xuất, không phải bằng chứng người đã duyệt.
- Backup `embedding_vs_bm25_backup_20261110_163750.csv` có 277 giá trị BM25 không parse được. Backup chỉ nằm trong kho lưu lịch sử/audit, không nằm trong allowlist đầu vào model; không sửa số bằng xóa dấu chấm.
- Trên working copy Windows, ba hash điểm/chú thích trong `experience_v2/run_info.json` khớp byte. Git blob LF khác hash cũ; biến thể UTF-8 BOM + CRLF khớp. Riêng hash nhãn không khớp cả bốn biến thể BOM/LF/CRLF. Giá trị nhãn và feature vẫn khớp các bảng training/prediction cũ.
- `.venv-embedding` hiện có Python 3.14.3, NumPy 2.5.4, scikit-learn 1.9.1, PyTorch 2.15.0, Sentence Transformers 6.2.0; `pip check` đạt. Backend dùng môi trường riêng.
- App có ownership CV, snapshot ứng tuyển, lọc JD Published/chưa hết hạn và API phân trang. Chưa có PDF extraction chuyên môn/recommendation. Seed PDF trang trắng và JD chung không đủ demo ML. Compose chỉ chạy trên VM Linux `192.168.123.136`.

## Những gì runner thực hiện

`jobapply_pilot_v1/run_baseline.py` tạo **thư mục chưa tồn tại**; run lỗi giữ lại `failure.json` và không được tái sử dụng tên. Run thành công có `manifest.json` với `status=complete`.

1. Snapshot byte nguyên vẹn dữ liệu và artifact lịch sử trong `inputs/`; snapshot code, lock và test trong `source/`. Ghi commit/branch, hash working code, kích thước, BOM và line endings. Commit chưa bao gồm thay đổi local được phân biệt rõ bằng source hashes.
2. Chuẩn hóa schema vào `labels_ai_draft.normalized.csv`. Giữ nguyên mọi ID, grade và rationale; `reviewer` trống, `annotation_origin=ai_draft`, `label_status=needs_review`. Hash phiên bản CV/JD dùng UTF-8 của `cv_text`/`match_text` sau khi đọc CSV với universal newlines. `label_schema_migration.json` ghi căn cứ và phần không biết.
3. Kiểm tra header/độ dài record, ID trống/trùng/lạ, lưới CV × JD đầy đủ, nhãn 0–1–2, điểm hữu hạn/phạm vi, rank là hoán vị 1..N và không trái thứ tự điểm. Đối chiếu selection manifest, nội dung JD ghép từ các mục và CV giữa CSV/TXT. Kiểm tra chú thích kinh nghiệm theo ID/scope, tháng và câu bằng chứng; việc câu có trong text **không xác nhận diễn giải chuyên môn là đúng**.
4. Kiểm tra lock môi trường và `pip check`. Khóa E5 tại revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, kiểm checksum weights/tokenizer/config trong `encoder.lock.json` trước khi load. Mặc định offline, CPU một thread, seed 0, thuật toán xác định; BM25 và E5 đều tính lại từ văn bản. File cosine cũ chỉ dùng đối chiếu.
5. Đánh giá keyword, BM25, E5, classifier hai feature, coverage control và experience classifier trên cùng leave-one-CV-out. Scaler chỉ fit train. k mặc định 5; CV/JD/k động, không khóa 6/50/300 trong đường chạy benchmark. `prepare_pilot.py` vẫn dựng pilot lịch sử cố định và cần nguồn upstream đang thiếu.
6. Ghi per-CV/macro metrics và số CV có metric xác định/bị loại. Không có nhãn 2 → Recall null; toàn nhãn 0 → NDCG null. Model refit phục vụ thí nghiệm có provenance/hash, không được đánh dấu model được chọn.
7. Đối chiếu score/rank/prediction và metric với lịch sử. `--compare-run` kiểm tra hash run tham chiếu rồi yêu cầu các bảng nhãn, điểm, dự đoán và metric của hai run mới giống byte. Kiểm tra input/code không đổi trong lúc chạy; hash toàn bộ artifact trước khi hoàn tất. `--verify-run` phát hiện sửa/mất/thêm file trong thư mục run.

CSV/JSON mới dùng UTF-8 không BOM, LF; snapshot input giữ byte gốc. Thư mục `results/reruns/` được Git/Docker ignore để tránh đưa nhiều bản sao dữ liệu vào commit/build. Báo cáo gọn để review nằm tại `docs/ml/reports/`.

`baseline_common.py` dùng chung validation/metrics/CSV; trainer trong experience v2 và `evaluate_top5.py` là entrypoint tương thích. Lệnh train/evaluate cũ phải truyền đường dẫn nhãn dẫn xuất; file nhãn lỗi schema bị từ chối thay vì lặng lẽ bỏ qua cột không tên.

## Chạy bằng PowerShell từ root repo

Môi trường đã đo là Windows AMD64, CPython **3.14.3**. Lock khóa toàn bộ phiên bản đang cài, gồm dependency bắc cầu. Chưa xác nhận cài mới trên máy sạch hoặc Linux; không dùng lock này để khẳng định tái tạo đa nền tảng. Weight/tokenizer có checksum riêng; lock dependency chưa đóng gói wheel hay hash wheel.

Nếu tạo môi trường riêng mới, dùng bản CPython 3.14.3 đúng kiến trúc rồi:

```powershell
Set-Location D:\JobApply
python -m venv .venv-ml
& .\.venv-ml\Scripts\python.exe -m pip install -r .\jobapply_pilot_v1\requirements-ml-win-py314.lock.txt
& .\.venv-ml\Scripts\python.exe -m pip check
```

Với môi trường ML hiện có:

```powershell
$mlPython = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$firstRun = ".\jobapply_pilot_v1\results\reruns\${runId}_baseline"
$secondRun = ".\jobapply_pilot_v1\results\reruns\${runId}_repeat"
& $mlPython .\jobapply_pilot_v1\run_baseline.py --output $firstRun --k 5
if ($LASTEXITCODE -ne 0) { throw 'First run failed; inspect failure.json.' }
& $mlPython .\jobapply_pilot_v1\run_baseline.py --output $secondRun --k 5 --compare-run $firstRun
if ($LASTEXITCODE -ne 0) { throw 'Repeat run failed; inspect artifacts.' }
& $mlPython .\jobapply_pilot_v1\run_baseline.py --verify-run $secondRun
```

Nếu cache E5 chưa có, thêm `--allow-download` vào run đầu; chỉ tải revision/file nằm trong encoder lock. Mặc định không truy cập mạng. Cache weights không chép vào repo; muốn chạy offline trên máy khác cần chuyển/cache đúng các file đã khóa.

Đánh giá riêng file CSV, hoặc train lại từ điểm đã có, không encode lại:

```powershell
& $mlPython .\jobapply_pilot_v1\evaluate_topk.py --labels "$firstRun\labels_ai_draft.normalized.csv" --rankings "$firstRun\embedding_vs_bm25.csv" --k 5
& $mlPython .\jobapply_pilot_v1\train_matcher.py --labels "$firstRun\labels_ai_draft.normalized.csv" --scores "$firstRun\embedding_vs_bm25.csv" --output ".\jobapply_pilot_v1\results\reruns\${runId}_train" --k 5
& $mlPython .\jobapply_pilot_v1\jobapply_experience_v2\run_experiment.py --pilot "$firstRun\inputs" --notes "$firstRun\inputs\jobapply_experience_v2" --labels "$firstRun\labels_ai_draft.normalized.csv" --scores "$firstRun\embedding_vs_bm25.csv" --output ".\jobapply_pilot_v1\results\reruns\${runId}_experience" --k 5
& $mlPython -m unittest discover -s tests/ml -v
```

Chạy runner đầy đủ để có manifest/provenance toàn run. Các CLI nhỏ dùng cho chẩn đoán; không tự tạo đầy đủ manifest. Bộ test ML dùng unittest riêng, không cần backend/DB. Khi chạy pytest backend mà thiếu ML dependencies, module ML được skip rõ lý do.

## Phần vẫn cần con người và dữ liệu bổ sung

- Người có chuyên môn duyệt rubric, relevance và bằng chứng; chấm độc lập/phân xử. Tên cột `reviewer` được dựng lại không tạo reviewer hay trạng thái đã duyệt.
- Rà scope/thời lượng kinh nghiệm, điều kiện bắt buộc/ưu tiên và quy ước “trên 3 năm” → 37 tháng. Chú thích hiện tại do trợ lý tạo cho pilot.
- Khôi phục lịch sử checksum nhãn từ nguồn có bằng chứng; không sửa `run_info.json` cũ để làm cho khớp.
- Bổ sung ba CSV upstream cùng script làm sạch, provenance/quyền sử dụng. Run này bắt đầu từ pilot, không tái tạo từ nguồn 3.101 JD.
- CV/JD độc lập và nhãn được xác minh vẫn thuộc Mốc 1–2. Metric ở đây chỉ đo đồng thuận với nhãn thử nghiệm.

Docker Compose, migrations, CV/database VM và deployment không được chạy hoặc thay đổi trong công việc Mốc 0.

## Kết quả thực chạy ngày 12/11/2026

Run bàn giao: `jobapply_pilot_v1/results/reruns/20261112_baseline_03`, so với `_02`. `_01` là run phát triển trước khi thêm khóa checksum encoder và các kiểm tra bổ sung; vẫn giữ nguyên để truy vết.

| Phương pháp | Recall@5 | NDCG@5 |
|---|---:|---:|
| Keyword | 0,2778 | 0,3518 |
| BM25 | 0,3016 | 0,4493 |
| E5 | 0,5476 | 0,6748 |
| Classifier hai feature | 0,5476 | 0,6678 |
| Coverage control | 0,5476 | 0,6458 |
| Experience classifier | 0,6270 | 0,7661 |

Mỗi macro có 6 CV xác định, 0 bị loại. Đây là số đo theo nhãn AI; bảng không chọn model để triển khai.

- Hai run `_02` và `_03`: bảy bảng nhãn dẫn xuất, điểm/ranking, per-CV/macro và held-out predictions **giống byte**. Cả hai manifest đều vượt kiểm tra hash; **33 file input/artifact gốc giữ nguyên byte hash**.
- So với lịch sử: toàn bộ rank BM25/keyword/E5/classifier giữ nguyên; 36 giá trị metric của supervised và 60 của experience khớp với tolerance tuyệt đối `1e-12`.
- Điểm BM25 khớp tuyệt đối. Cosine lệch tối đa khoảng `1e-6`; điểm classifier lệch tối đa `2,5281e-5`. Báo cáo giữ số điểm vượt tolerance `1e-6`, không sửa điểm hay đổi nhãn để làm khớp. Không có đủ cấu hình encoder/thread lịch sử để kết luận nguyên nhân duy nhất. Hai run mới chứng minh khả năng lặp lại với cấu hình mới đã khóa, không khôi phục trọn lịch sử cũ.
- **11 test ML đạt**, gồm schema/record/ID lỗi, điểm NaN/Inf/chuỗi hỏng, thiếu cặp, rank sai, metric null, bảo toàn nhãn, tập 3 CV × 3 JD/k=2, không dùng nhãn held-out để train, kinh nghiệm unknown/strict threshold, chia dòng dài, hash và chống ghi đè.
- **4 test cấu hình backend đạt**; khi chạy bằng môi trường backend, module ML skip rõ vì thiếu dependency ML. Có cảnh báo deprecation Starlette/httpx sẵn có. Lint `ruff --select F,E9` trên code ML sửa/thêm và tests đạt; `git diff --check` đạt. Không chạy lại workflow backend, frontend E2E hoặc Docker/VM vì không sửa các luồng đó.

Bằng chứng máy đọc: [receipt/config/hash/audit/regression](reports/20261112-baseline.json), [macro](reports/20261112-macro_metrics.csv), [theo CV](reports/20261112-metrics_by_cv.csv). Receipt chứa hash manifest của cả hai run và toàn bộ hash artifact run bàn giao, để đối chiếu khi chuyển kho run sang máy khác. Không đặt file thêm vào thư mục run đã hoàn tất; báo cáo bổ sung nằm ngoài run.
