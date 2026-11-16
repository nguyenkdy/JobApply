"""Publish metadata-only results from sealed experiment and inference release."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import file_hash, fresh_folder, read_json, require, verify, write_csv, write_json


def build(run, package, package_check, output):
    run, package = Path(run).resolve(), Path(package).resolve()
    verify(run, "step4-experiment")
    verify(package, "step4-model")
    verification = read_json(Path(package_check) / "verification.json")
    require(verification["package_manifest_sha256"] == file_hash(package / "manifest.json"), "Wrong release verification")
    r = read_json(run / "summary.json")
    selection = read_json(run / "selection.json")
    require(selection["selected"] == r["selected"] and not selection["test_metrics_seen"] and not selection["test_scores_seen"],
            "Selection receipt is inconsistent")
    require(file_hash(run / "selection.json") == r["selection_sha256"] == read_json(package / "release.json")["selection_sha256"], "Selection changed")
    out = fresh_folder(output, (run, package))
    public = dict(r, run=str(run), package=str(package), experiment_manifest_sha256=file_hash(run / "manifest.json"),
                  release_verification=verification, encoder=read_json(run / "encoder.lock.json"),
                  environment=read_json(run / "environment.json"))
    write_json(out / "20261114-step4-results.json", public)
    table = []
    for method, test in r["test_comparison"].items():
        val = r["validation_comparison"][method]
        table.append(dict(method=method, selected=method == r["selected"]["name"],
            validation_ndcg5=val["ndcg5"], validation_recall5_ge2=val["recall5_ge2"], test_ndcg5=test["ndcg5"],
            test_recall5_ge2=test["recall5_ge2"], test_recall5_ge1=test["recall5_ge1"],
            test_recall2_cv_defined=test["recall5_ge2_defined"], test_recall2_cv_undefined=test["recall5_ge2_undefined"]))
    write_csv(out / "20261114-step4-comparison.csv", table, tuple(table[0]))
    def number(value):
        return "không xác định" if value is None else f"{value:.4f}"
    lines = "\n".join(f"| {'**' + t['method'] + '**' if t['selected'] else t['method']} | {number(t['validation_ndcg5'])} | {number(t['test_ndcg5'])} | {number(t['test_recall5_ge2'])} | {number(t['test_recall5_ge1'])} |" for t in table)
    chosen = r["selected"]["name"]
    test = read_json(run / "test.json")[chosen]
    slice_rows = "\n".join(f"| {field}: {name} | {m['cv_count']} | {number(m['ndcg5'])} | {number(m['recall5_ge2'])} | {m['recall5_ge2_defined']} |"
                           for field in ("role", "experience_kind", "template_family") for name, m in test["slices"][field].items())
    diagnostic = test["diagnostics"]
    positive2 = [q["positives_ge2"] for q in test["by_cv"] if q["positives_ge2"]]
    strict_ceiling = sum(min(5, n)/n for n in positive2)/len(positive2)
    interpretation = ("Model được chọn chỉ dùng metadata. Trên bộ nhãn này, chưa có căn cứ ưu tiên E5/BM25 trong cấu hình thắng; kết quả chủ yếu đo khả năng khôi phục các quy tắc role/skill/stack/experience đã dùng tạo nhãn."
                      if r["selected"]["family"] == "metadata" else
                      "Model được chọn thắng theo validation của benchmark này; không suy ra nó tối ưu trên ứng viên thật. So sánh ablation và baseline luật trước khi kết luận phần cải thiện đến từ ngữ nghĩa văn bản.")
    text = f"""# Bước 4 — Kết quả thí nghiệm offline, 14/11/2026

**Đã chạy Bước 4. Model chọn trên validation: `{chosen}`.** Không chọn lại theo test, không refit bằng validation/test, không đổi CV/JD/nhãn/split. [Receipt đầy đủ](reports/20261114-step4-results.json), [bảng CSV](reports/20261114-step4-comparison.csv).

## Dữ liệu và protocol

60 CV synthetic mới / 12 họ; train 30 CV × 50 JD = 1.500 cặp, validation/test mỗi tập 15 CV × 50 JD = 750 cặp. 60 CV cũ giữ development. Đây là known-jd trên catalog 50 JD cố định, không phải thử nghiệm trên toàn bộ 788 JD hoặc JD mới. Nhãn `automatic_rule_proxy` giữ nguyên.

Protocol được ghi trước khi tính điểm: NDCG@5 macro là chính; hòa thì Recall@5 nhãn ≥2, sau đó ưu tiên họ model đơn giản hơn và C nhỏ hơn. Các metric được làm tròn 12 chữ số cho tie-break. Thứ tự đơn giản: keyword, BM25, E5, LR metadata, LR text, LR combined. Có 12 cấu hình ứng viên và một baseline luật chẩn đoán. `selection.json` được ghi trước khi tính điểm test; hash `{r['selection_sha256']}` được kiểm lại cuối run.

E5 dùng `intfloat/multilingual-e5-base`, revision `{public['encoder']['revision']}`, CPU, 2 thread, batch 4, prefix query/passage, token limit 512. Văn bản dài chia đoạn; trung bình vector đoạn theo số token rồi chuẩn hóa. Đây là lựa chọn pooling của dự án, chưa chứng minh tối ưu. Xem [model card nguồn](https://huggingface.co/intfloat/multilingual-e5-base) và [lock từng file](data_configs/step4_encoder.lock.json).

Logistic Regression dùng StandardScaler fit **chỉ trên train**, C ∈ {{0,1; 1; 10}}, `class_weight=balanced`, solver lbfgs, seed 20261113, max_iter 3000. Score là P(1)+2P(2). Text: BM25/E5. Metadata: khớp nghề, coverage skill/stack, cờ thiếu dữ liệu, coverage thời lượng đúng scope, gap năm quan sát được và vi phạm cận nghiêm ngặt. Combined ghép hai nhóm. Không dùng ID, tên, tuổi, giới tính, địa chỉ hoặc nhãn làm feature.

## So sánh kết quả

Mỗi họ LR chọn C bằng validation trước khi xem test. Baseline luật không tham gia chọn model vì nó định nghĩa nhãn đích; điểm cao của baseline đó không phải bằng chứng đánh giá độc lập.

| Phương pháp | NDCG@5 validation | NDCG@5 test | Recall@5 test, nhãn ≥2 | Recall@5 test, nhãn ≥1 |
|---|---:|---:|---:|---:|
{lines}

{interpretation}

NDCG dùng gain 2^label−1 và có mẫu số 15 CV ở validation/test. **Recall nhãn ≥2 chỉ tính trên 6/15 CV mỗi tập; 9 CV không có positive được báo là undefined**, không thay bằng 0/1. Với nhãn ≥1, mỗi CV có 10 positive nên trần Recall@5 là 0,5. Chỉ có ba họ template mỗi tập validation/test, nên các khác biệt nhỏ chưa đáng tin cậy để suy rộng.

Trần Recall@5 nhãn ≥2 trên test từ số positive thực tế là **{strict_ceiling:.4f}**: {sum(n > 5 for n in positive2)} CV có hơn năm JD nhãn 2. Vì vậy NDCG đạt 1 không đòi hỏi Recall@5 phải bằng 1. Điểm 1 ở đây là xếp hạng lý tưởng theo **nhãn proxy đang dùng**, không phải “độ chính xác tuyển dụng 100%”.

## Phân bố kết quả model được chọn trên test

| Nhóm | CV | NDCG@5 | Recall@5 nhãn ≥2 | CV có mẫu số Recall |
|---|---:|---:|---:|---:|
{slice_rows}

Chẩn đoán trong {diagnostic['top5_slots']} vị trí Top 5: {diagnostic['label_zero_in_top5']} nhãn 0; {diagnostic['different_role_in_top5']} khác nghề; {diagnostic['same_role_disjoint_stack_in_top5']} cùng nghề nhưng không giao stack; {diagnostic['partial_or_unknown_experience_in_top5']} thiếu/không đủ scope thời lượng để đối chiếu toàn bộ; {diagnostic['observed_experience_gap_in_top5']} có gap/cận kinh nghiệm không đạt. Các nhóm chồng nhau; đây là dấu hiệu theo metadata, không phải lỗi do chuyên gia xác nhận. Unknown không tự thành không phù hợp.

## Tính ổn định, đóng gói và giới hạn

- Mã hóa lại hai CV train: max delta `{r['encoder_repeat_max_abs_delta']}`, ngưỡng 1e-6. Không chạy hai thí nghiệm test để chọn lần tốt hơn.
- Lưu/load model giữ nguyên điểm validation. Gói suy luận hoàn chỉnh được kiểm lại trên {verification['validation_cv_count']} CV validation: Top 5 giống nhau, max score delta `{verification['max_score_delta']}`. Không fit hoặc chọn model lần nữa.
- Probe ba biến thể metadata cá nhân trên hai CV train cho các phương pháp cuối cùng giữ nguyên điểm/Top 5. Đây là kiểm tra allowlist cấu trúc với văn bản chuyên môn không đổi; **chưa kiểm PDF/raw text, phân biệt đối xử theo nhóm hoặc fairness đầu cuối**.
- Run chuẩn bị, ba CSV gốc và 51 file pilot không đổi. Manifest/code snapshot/environment lock/encoder hash được lưu. Không đổi API/UI/Docker/VM và không nhập JD lịch sử vào database app.
- Dữ liệu synthetic cùng một tác giả; nhãn tự động phụ thuộc role/stack/experience, không phải gold. Metadata tốt trên nhãn này có thể chỉ là học lại bộ luật, chưa chứng minh phù hợp tuyển dụng thực tế. Data Analyst vẫn chờ JD ngoài development đủ chất lượng; không bị bỏ khỏi mục tiêu nghiên cứu.

Run: `{run}`. Gói suy luận đầy đủ: `{package}`. Gói có model đã chọn (nếu là LR), 50 JD, vector JD, evidence scope/cận, encoder weights, runtime source, environment lock và manifest. Bản `model_package` trong run là snapshot thí nghiệm; dùng **gói release đầy đủ** để suy luận vì có thêm receipt JD và lock toàn môi trường. Gói chỉ nhận professional text/metadata đã chuẩn hóa, chưa có parser CV/PDF tổng quát.

Tổng thời gian run {r['timings']['total_seconds']:.1f} giây; đây là thời gian chạy lô trên máy local, không phải latency API. Thời gian từng giai đoạn/chunk trong receipt.

## PowerShell

```powershell
Set-Location D:\\JobApply
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data verify --artifact .\\ml_data_runs\\20261114_step4_v1_01
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data verify --artifact .\\ml_data_runs\\20261114_step4_release_v1
```

Tái tạo run mới với protocol đã khóa, **không dùng kết quả test để sửa cấu hình**:

```powershell
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe .\\scripts\\fetch-step4-encoder.py
if ($LASTEXITCODE -ne 0) {{ throw 'Encoder verification failed' }}
$expOut = '.\\ml_data_runs\\step4_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_experiment --preparation .\\ml_data_runs\\20261114_pretraining_v3_01 --encoder .\\.tools\\ml-models\\multilingual-e5-base-d1287505 --output $expOut
if ($LASTEXITCODE -ne 0) {{ throw 'Experiment failed' }}
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe .\\scripts\\release-step4-model.py --run $expOut --output "${{expOut}}_release" --verification-output "${{expOut}}_release_check"
if ($LASTEXITCODE -ne 0) {{ throw 'Release verification failed' }}
```

Suy luận offline với một file JSON CV đã chuẩn hóa:

```powershell
$predictionOut = '.\\ml_data_runs\\prediction_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_experiment.predict --package .\\ml_data_runs\\20261114_step4_release_v1 --cv-json .\\my_professional_cv.json --output $predictionOut
if ($LASTEXITCODE -ne 0) {{ throw 'Prediction failed' }}
```

`my_professional_cv.json` là đầu vào người dùng cần chuẩn bị, chưa có sẵn. Schema: `text_normalized` (văn bản chuyên môn ≥80 ký tự), `text_scope="professional"`, `role` (chuỗi), `skills`/`stack` (list thuật ngữ chuẩn hóa), `experience` (dictionary scope → tháng có evidence; unknown `{{}}`), `lineage.experience_kind` (`employment`, `contract`, `project`, `internship`, `unknown`). Có thể lấy record CV trong `documents.json` để thử lại; đó chỉ là demo dữ liệu đã biết. Không tự suy thời gian công nghệ từ tổng năm hoặc coi output là đánh giá ứng viên thật. Gói model là artifact local tin cậy đã tạo; không load pickle từ nguồn không tin cậy.

Code mới ở `ml_experiment/`, các script fetch/release/report, test `tests/ml/test_step4.py`. Artifact đầy đủ nằm trong `ml_data_runs/` và encoder trong `.tools/`, đều Git ignore. Chỉ báo cáo/config/code được đưa vào cây nguồn. Xem [TESTING.md](../../TESTING.md).
"""
    (out / "step4_results.md").write_text(text, encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "package", "package-check", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(build(args.run, args.package, args.package_check, args.output))
