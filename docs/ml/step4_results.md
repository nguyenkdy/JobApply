# Bước 4 — Kết quả thí nghiệm offline, 14/11/2026

**Đã chạy Bước 4. Model chọn trên validation: `lr_metadata_C0.1`.** Không chọn lại theo test, không refit bằng validation/test, không đổi CV/JD/nhãn/split. [Receipt đầy đủ](reports/20261114-step4-results.json), [bảng CSV](reports/20261114-step4-comparison.csv).

## Dữ liệu và protocol

60 CV synthetic mới / 12 họ; train 30 CV × 50 JD = 1.500 cặp, validation/test mỗi tập 15 CV × 50 JD = 750 cặp. 60 CV cũ giữ development. Đây là known-jd trên catalog 50 JD cố định, không phải thử nghiệm trên toàn bộ 788 JD hoặc JD mới. Nhãn `automatic_rule_proxy` giữ nguyên.

Protocol được ghi trước khi tính điểm: NDCG@5 macro là chính; hòa thì Recall@5 nhãn ≥2, sau đó ưu tiên họ model đơn giản hơn và C nhỏ hơn. Các metric được làm tròn 12 chữ số cho tie-break. Thứ tự đơn giản: keyword, BM25, E5, LR metadata, LR text, LR combined. Có 12 cấu hình ứng viên và một baseline luật chẩn đoán. `selection.json` được ghi trước khi tính điểm test; hash `771f75f9d41462262d46dcf584ee0c592039d7eaccf937bbe1f07197bd7e0473` được kiểm lại cuối run.

E5 dùng `intfloat/multilingual-e5-base`, revision `d128750597153bb5987e10b1c3493a34e5a4502a`, CPU, 2 thread, batch 4, prefix query/passage, token limit 512. Văn bản dài chia đoạn; trung bình vector đoạn theo số token rồi chuẩn hóa. Đây là lựa chọn pooling của dự án, chưa chứng minh tối ưu. Xem [model card nguồn](https://huggingface.co/intfloat/multilingual-e5-base) và [lock từng file](data_configs/step4_encoder.lock.json).

Logistic Regression dùng StandardScaler fit **chỉ trên train**, C ∈ {0,1; 1; 10}, `class_weight=balanced`, solver lbfgs, seed 20261113, max_iter 3000. Score là P(1)+2P(2). Text: BM25/E5. Metadata: khớp nghề, coverage skill/stack, cờ thiếu dữ liệu, coverage thời lượng đúng scope, gap năm quan sát được và vi phạm cận nghiêm ngặt. Combined ghép hai nhóm. Không dùng ID, tên, tuổi, giới tính, địa chỉ hoặc nhãn làm feature.

## So sánh kết quả

Mỗi họ LR chọn C bằng validation trước khi xem test. Baseline luật không tham gia chọn model vì nó định nghĩa nhãn đích; điểm cao của baseline đó không phải bằng chứng đánh giá độc lập.

| Phương pháp | NDCG@5 validation | NDCG@5 test | Recall@5 test, nhãn ≥2 | Recall@5 test, nhãn ≥1 |
|---|---:|---:|---:|---:|
| bm25 | 0.1933 | 0.2221 | 0.2222 | 0.1200 |
| e5 | 0.5548 | 0.5470 | 0.1944 | 0.3200 |
| keyword | 0.2148 | 0.2354 | 0.1944 | 0.1200 |
| lr_combined_C1 | 1.0000 | 1.0000 | 0.9444 | 0.5000 |
| **lr_metadata_C0.1** | 1.0000 | 1.0000 | 0.9444 | 0.5000 |
| lr_text_C0.1 | 0.6039 | 0.6006 | 0.3194 | 0.3267 |
| rule_proxy | 1.0000 | 1.0000 | 0.9444 | 0.5000 |

Model được chọn chỉ dùng metadata. Trên bộ nhãn này, chưa có căn cứ ưu tiên E5/BM25 trong cấu hình thắng; kết quả chủ yếu đo khả năng khôi phục các quy tắc role/skill/stack/experience đã dùng tạo nhãn.

NDCG dùng gain 2^label−1 và có mẫu số 15 CV ở validation/test. **Recall nhãn ≥2 chỉ tính trên 6/15 CV mỗi tập; 9 CV không có positive được báo là undefined**, không thay bằng 0/1. Với nhãn ≥1, mỗi CV có 10 positive nên trần Recall@5 là 0,5. Chỉ có ba họ template mỗi tập validation/test, nên các khác biệt nhỏ chưa đáng tin cậy để suy rộng.

Trần Recall@5 nhãn ≥2 trên test từ số positive thực tế là **0.9444**: 2 CV có hơn năm JD nhãn 2. Vì vậy NDCG đạt 1 không đòi hỏi Recall@5 phải bằng 1. Điểm 1 ở đây là xếp hạng lý tưởng theo **nhãn proxy đang dùng**, không phải “độ chính xác tuyển dụng 100%”.

## Phân bố kết quả model được chọn trên test

| Nhóm | CV | NDCG@5 | Recall@5 nhãn ≥2 | CV có mẫu số Recall |
|---|---:|---:|---:|---:|
| role: backend java | 3 | 1.0000 | 1.0000 | 1 |
| role: backend python | 3 | 1.0000 | 1.0000 | 1 |
| role: devops/cloud | 3 | 1.0000 | 1.0000 | 2 |
| role: frontend | 3 | 1.0000 | 0.8333 | 1 |
| role: qa/testing | 3 | 1.0000 | 0.8333 | 1 |
| experience_kind: contract | 3 | 1.0000 | 0.9444 | 3 |
| experience_kind: employment | 3 | 1.0000 | 0.9444 | 3 |
| experience_kind: internship | 3 | 1.0000 | không xác định | 0 |
| experience_kind: project | 3 | 1.0000 | không xác định | 0 |
| experience_kind: unknown | 3 | 1.0000 | không xác định | 0 |
| template_family: evidence_matrix | 5 | 1.0000 | 1.0000 | 2 |
| template_family: milestone_cards | 5 | 1.0000 | 1.0000 | 2 |
| template_family: service_retrospective | 5 | 1.0000 | 0.8333 | 2 |

Chẩn đoán trong 75 vị trí Top 5: 0 nhãn 0; 0 khác nghề; 9 cùng nghề nhưng không giao stack; 47 thiếu/không đủ scope thời lượng để đối chiếu toàn bộ; 0.0 có gap/cận kinh nghiệm không đạt. Các nhóm chồng nhau; đây là dấu hiệu theo metadata, không phải lỗi do chuyên gia xác nhận. Unknown không tự thành không phù hợp.

## Tính ổn định, đóng gói và giới hạn

- Mã hóa lại hai CV train: max delta `2.6446650736033916e-07`, ngưỡng 1e-6. Không chạy hai thí nghiệm test để chọn lần tốt hơn.
- Lưu/load model giữ nguyên điểm validation. Gói suy luận hoàn chỉnh được kiểm lại trên 2 CV validation: Top 5 giống nhau, max score delta `0.0`. Không fit hoặc chọn model lần nữa.
- Probe ba biến thể metadata cá nhân trên hai CV train cho các phương pháp cuối cùng giữ nguyên điểm/Top 5. Đây là kiểm tra allowlist cấu trúc với văn bản chuyên môn không đổi; **chưa kiểm PDF/raw text, phân biệt đối xử theo nhóm hoặc fairness đầu cuối**.
- Run chuẩn bị, ba CSV gốc và 51 file pilot không đổi. Manifest/code snapshot/environment lock/encoder hash được lưu. Không đổi API/UI/Docker/VM và không nhập JD lịch sử vào database app.
- Dữ liệu synthetic cùng một tác giả; nhãn tự động phụ thuộc role/stack/experience, không phải gold. Metadata tốt trên nhãn này có thể chỉ là học lại bộ luật, chưa chứng minh phù hợp tuyển dụng thực tế. Data Analyst vẫn chờ JD ngoài development đủ chất lượng; không bị bỏ khỏi mục tiêu nghiên cứu.

Run: `D:\JobApply\ml_data_runs\20261114_step4_v1_01`. Gói suy luận đầy đủ: `D:\JobApply\ml_data_runs\20261114_step4_release_v1`. Gói có model đã chọn (nếu là LR), 50 JD, vector JD, evidence scope/cận, encoder weights, runtime source, environment lock và manifest. Bản `model_package` trong run là snapshot thí nghiệm; dùng **gói release đầy đủ** để suy luận vì có thêm receipt JD và lock toàn môi trường. Gói chỉ nhận professional text/metadata đã chuẩn hóa, chưa có parser CV/PDF tổng quát.

Tổng thời gian run 273.1 giây; đây là thời gian chạy lô trên máy local, không phải latency API. Thời gian từng giai đoạn/chunk trong receipt.

## PowerShell

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data verify --artifact .\ml_data_runs\20261114_step4_v1_01
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data verify --artifact .\ml_data_runs\20261114_step4_release_v1
```

Tái tạo run mới với protocol đã khóa, **không dùng kết quả test để sửa cấu hình**:

```powershell
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe .\scripts\fetch-step4-encoder.py
if ($LASTEXITCODE -ne 0) { throw 'Encoder verification failed' }
$expOut = '.\ml_data_runs\step4_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_experiment --preparation .\ml_data_runs\20261114_pretraining_v3_01 --encoder .\.tools\ml-models\multilingual-e5-base-d1287505 --output $expOut
if ($LASTEXITCODE -ne 0) { throw 'Experiment failed' }
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe .\scripts\release-step4-model.py --run $expOut --output "${expOut}_release" --verification-output "${expOut}_release_check"
if ($LASTEXITCODE -ne 0) { throw 'Release verification failed' }
```

Suy luận offline với một file JSON CV đã chuẩn hóa:

```powershell
$predictionOut = '.\ml_data_runs\prediction_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_experiment.predict --package .\ml_data_runs\20261114_step4_release_v1 --cv-json .\my_professional_cv.json --output $predictionOut
if ($LASTEXITCODE -ne 0) { throw 'Prediction failed' }
```

`my_professional_cv.json` là đầu vào người dùng cần chuẩn bị, chưa có sẵn. Schema: `text_normalized` (văn bản chuyên môn ≥80 ký tự), `text_scope="professional"`, `role` (chuỗi), `skills`/`stack` (list thuật ngữ chuẩn hóa), `experience` (dictionary scope → tháng có evidence; unknown `{}`), `lineage.experience_kind` (`employment`, `contract`, `project`, `internship`, `unknown`). Có thể lấy record CV trong `documents.json` để thử lại; đó chỉ là demo dữ liệu đã biết. Không tự suy thời gian công nghệ từ tổng năm hoặc coi output là đánh giá ứng viên thật. Gói model là artifact local tin cậy đã tạo; không load pickle từ nguồn không tin cậy.

Code mới ở `ml_experiment/`, các script fetch/release/report, test `tests/ml/test_step4.py`. Artifact đầy đủ nằm trong `ml_data_runs/` và encoder trong `.tools/`, đều Git ignore. Chỉ báo cáo/config/code được đưa vào cây nguồn. Xem [TESTING.md](../../TESTING.md).
