"""Publish the pre-Step-4 handoff from two complete immutable preparation runs."""
import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, csv_rows, file_hash, fresh_folder, read_json, require, verify, write_json


def build(first, second, output):
    first, second = Path(first).resolve(), Path(second).resolve()
    for path in (first, second):
        verify(path, "pretraining-ready")
    hashes = [{p.relative_to(folder).as_posix(): file_hash(p) for p in folder.rglob("*") if p.is_file()}
              for folder in (first, second)]
    require(hashes[0] == hashes[1], "Preparation runs differ; cannot claim exact reproducibility")
    r = read_json(first / "handoff_report.json")
    before = read_json(first / "protected_input_hashes.json")
    require(all(file_hash(ROOT / name) == expected for name, expected in before.items()), "Original source/pilot changed")
    train_labels = {p["pair_id"]: p for p in csv_rows(first / "train_labels/pairs.csv")[1]}
    diagnostic = csv_rows(first / "train_sampling_diagnostic/pairs.csv")[1]
    require(all(p["pair_id"] in train_labels and p["cv_version"] == train_labels[p["pair_id"]]["cv_version"]
                and p["jd_version"] == train_labels[p["pair_id"]]["jd_version"] for p in diagnostic), "Sampling diagnostic is not a subset of training census")
    positive_counts, strict_coverage = {}, {}
    for partition in ("train", "validation", "test"):
        rows = csv_rows(first / (partition + "_labels") / "pairs.csv")[1]
        counts = Counter(p["cv_id"] for p in rows if int(p["relevance_0_1_2"]) >= 1)
        require(set(counts) == {p["cv_id"] for p in rows} and set(counts.values()) == {10},
                "Recall ceiling claim no longer matches the labels")
        positive_counts[partition] = dict(sorted(counts.items()))
        strict = Counter(p["cv_id"] for p in rows if p["relevance_0_1_2"] == "2")
        strict_coverage[partition] = dict(cv_count=len(counts), cv_with_label_two=len(strict),
                                          cv_without_label_two=len(counts)-len(strict))
    folder = fresh_folder(output, (first, second))
    receipt = dict(r, reproducibility=dict(run_paths=[p.relative_to(ROOT).as_posix() for p in (first, second)],
        files_identical=len(hashes[0]), all_bytes_identical=True, manifest_sha256=file_hash(first / "manifest.json")),
        diagnostic_candidates_resolve_to_train_labels=len(diagnostic),
        positives_per_cv_at_relevance_one=positive_counts, label_two_query_coverage=strict_coverage)
    write_json(folder / "20261114-pretraining-ready.json", receipt)
    config = read_json(first / "import_config.json")
    for item in config["sources"] + config["context_files"] + config["historical_cv_sources"]:
        item["path"] = "../../../" + (first / item["path"]).resolve().relative_to(ROOT).as_posix()
    write_json(folder / "pretraining_v3_import.json", config)
    distribution = r["distributions"]
    readiness = r["readiness"]
    rows = "\n".join(f"| {p} | {distribution[p]['cv_count']} | {distribution[p]['group_count']} | {readiness['pair_counts'][p]} | "
                     f"{readiness['class_counts'][p].get('0', 0)} / {readiness['class_counts'][p].get('1', 0)} / {readiness['class_counts'][p].get('2', 0)} |"
                     for p in ("train", "validation", "test"))
    family_rows = "\n".join(f"- **{p}:** `{', '.join(distribution[p]['template_families'])}`; mỗi nghề {distribution[p]['cv_count']//5} CV và mỗi loại kinh nghiệm {distribution[p]['cv_count']//5} CV."
                            for p in ("train", "validation", "test"))
    strict_text = "; ".join(f"{p}: {c['cv_with_label_two']}/{c['cv_count']} CV có ít nhất một nhãn 2, {c['cv_without_label_two']} CV không có"
                            for p, c in strict_coverage.items())
    text = f"""# Bàn giao dữ liệu trước Bước 4 — 14/11/2026

**Đã hoàn tất điều kiện kỹ thuật cho thí nghiệm synthetic với nhãn tự động. Đã dừng trước Bước 4.** Không chạy BM25/E5, không fit model, không chọn model theo validation, chưa tính metric test. [Receipt sinh từ run thực](reports/20261114-pretraining-ready.json), [config import](data_configs/pretraining_v3_import.json).

## Dữ liệu đã chuẩn bị

- Lô 60 CV v2 cũ giữ nguyên nội dung, được chuyển sang development trong **bản dẫn xuất mới**, có nhật ký exposure. Run cũ không sửa. Toàn bộ 60 CV v1 được thêm làm tham chiếu development để phát hiện trùng/gần trùng và lineage; sáu CV pilot vẫn được bảo vệ.
- Viết **60 CV mới** trong `ml_data_assets/independent_cv_v3/`: 12 CV/nghề cho Backend Python, Backend Java, Frontend, DevOps/Cloud, QA/Testing. 12 khung nội dung được mô tả trước khi viết; mỗi khung có năm CV, một CV/nghề và một hồ sơ cho mỗi loại employment/project/internship/contract/unknown. Không lấy CV cũ rồi đổi tên khung, không xem ranking hoặc JD đích để viết CV.
- Metadata kỹ năng và thời lượng trỏ tới evidence nguyên văn/offset. Alias scope Việt–Anh có phiên bản; thời gian nghề/phát triển phần mềm không cấp thời gian cho từng công nghệ. Có 12 CV thiếu mốc thời gian giữ `{{}}`. Các CV đều synthetic và cùng một tác giả AI/cohort; **12 nhóm lineage không đồng nghĩa 12 nguồn ứng viên thật độc lập**.
- Kho JD giữ nguyên 3.062 record: 888 keep, 65 trùng loại, 2.109 quarantine; 100 keep development và 788 keep ngoài development. Toàn bộ 154 record thuộc nhóm development giữ nguyên. Catalog thí nghiệm vẫn đúng **50 ID cũ, 10 JD/nghề**, không chọn lại theo nhãn hoặc seed khác. Cả train và đánh giá chỉ dùng catalog này.
- Trích xuất JD giữ câu có AND/OR, ưu tiên và trường hợp logic trộn/chưa phân giải. Không biến danh sách mơ hồ thành tất cả bắt buộc. Catalog còn `{r['catalogue']['missing_metadata']}` metadata thiếu, trong đó 7 JD chưa có ngưỡng kinh nghiệm dùng được; giữ unknown.

## Split và nhãn đã tạo

Seed `20261113`, một lần phân bổ theo nguyên nhóm. Tỷ lệ đích 60/20/20 được làm tròn theo nhóm và giữ tối thiểu mỗi tập, nên kết quả là **30/15/15**, không ép thành 30/20/10. Kiểm tra nối với nguồn/template lịch sử và gần trùng giữ nguyên 12 nhóm mới, mỗi nhóm năm CV.

| Tập | CV mới | Nhóm | Cặp trên 50 JD | Nhãn 0 / 1 / 2 |
|---|---:|---:|---:|---|
{rows}

{family_rows}

**Train dùng toàn bộ lưới 1.500 cặp**, được quyết định trong design trước khi sinh nhãn, để không phụ thuộc việc sample có lấy được lớp hiếm hay không. Có thêm **{r['sampling_diagnostic']['pairs']} cặp random/hard** để kiểm tra chiến lược lấy mẫu: `{r['sampling_diagnostic']['by_strategy']}`. File candidate này để nhãn trống theo schema sampler; mọi `pair_id` đều tra được nhãn tương ứng trong `train_labels/pairs.csv`. Nó không phải tập huấn luyện khác hoặc dữ liệu chưa xử lý còn thiếu.

Quy tắc `{read_json(first / 'protocol.json')['labeler_version']}` được ghi rõ:

- **0:** hai nghề chính được xác định và khác nhau theo taxonomy.
- **1:** cùng nghề nhưng chỉ có tín hiệu một phần; gồm bộ công nghệ khác nhau đã biết, thiếu stack chung, hoặc thời lượng chưa đủ/không thể so sánh. Đây là *khả năng tương thích theo nghề*, không phải bằng chứng đáp ứng JD.
- **2:** cùng nghề, có stack chung và mọi ngưỡng thời lượng đã trích xuất đều có scope tương đương được CV chứng minh, đáp ứng cận `>`/`>=` tương ứng. Không khẳng định mọi điều kiện bắt buộc/AND/OR của JD đều đã được đáp ứng.
- Thiếu nghề hoặc thiếu hẳn kỹ năng từ nguồn vẫn `insufficient_evidence`, nhãn trống. Không đổi unknown thành 0. Trong lưới mới, điều kiện đủ để bộ luật cho nhãn số ở cả 3.000 cặp; không cần ép nhãn hay sửa CV sau khi xem kết quả.

Sửa so với v2: **hai tập kỹ năng đã biết nhưng không giao nhau không đồng nghĩa thiếu metadata**. Vai trò giống nhau là evidence cho mức 1 của proxy đã định nghĩa. Kinh nghiệm tổng nghề chỉ dùng nếu CV nói rõ tổng; yêu cầu thời gian công nghệ cần đúng scope đó. Thực tập/dự án không được quy thành số tháng nghề.

## Điều kiện đã kiểm chứng và giới hạn đánh giá

Tất cả {len(readiness['checks'])} gate đạt: nguồn lịch sử ngoài split mới, 60 CV mới keep, 12 nhóm không xuyên partition, mỗi tập đủ năm nghề/năm loại kinh nghiệm/nhiều họ, đúng toàn bộ lưới 50 JD, nhãn số đầy đủ và train có cả ba lớp. `ready_for_automatic_label_experiment=true`; `model_training_performed=false`, `final_test_evaluated=false`, `production_quality_established=false`.

Với rubric này, mỗi CV có 10 JD cùng nghề được gán 1 hoặc 2. Vì thế **Recall@5 với ngưỡng relevance ≥1 có trần 0,5** ngay cả khi năm kết quả đều thuộc nghề đúng. Đây là giới hạn từ thiết kế nhãn/catalog, **không phải điểm model đã chạy**. Bước 4 cần báo thêm ngưỡng nhãn 2, số CV không có positive, NDCG và baseline luật; không đánh giá model tốt/xấu chỉ bằng kỳ vọng Recall đạt 1.

Kiểm kê độ phủ nhãn 2 từ dữ liệu: **{strict_text}**. Recall ở ngưỡng 2 không xác định cho CV không có positive; phải công bố mẫu số, không tự gán 0/1. Cả ba tập có 80% cặp nhãn 0; lớp 2 hiếm. Không đổi CV/split/nhãn để làm đẹp phân bố.

Nhãn là `automatic_rule_proxy`, không phải gold; feature và nhãn cùng dựa trên role/stack/experience nên có nguy cơ học lại bộ luật. Protocol yêu cầu baseline luật và ablation text-only/metadata. Kết quả sau này chỉ áp dụng benchmark synthetic/catalog 50 JD; chưa suy rộng sang người thật, thị trường, 788 JD hoặc JD mới. Không có yêu cầu người review/calibration.

Data Analyst vẫn thuộc nghiên cứu: 9 tag nguồn, 8 dấu hiệu chức danh, 4 nối pilot, 0 ngoài pilot qua gate theo kiểm kê. Cần JD hợp lệ mới hoặc khôi phục nguồn có evidence trước khi thêm nghề thứ sáu; lô sửa parser vẫn development.

## Tái tạo và bảo toàn

Hai run `{first.relative_to(ROOT).as_posix()}` và `{second.relative_to(ROOT).as_posix()}` có **{len(hashes[0])}/{len(hashes[0])} file giống byte**. Ba CSV gốc, 51 file pilot và bốn run đầu vào lịch sử không đổi. Snapshot/config/source code/hash có trong manifest; dữ liệu đầy đủ và nhãn nằm trong `ml_data_runs/` đã Git ignore. Không commit dữ liệu nguồn lớn hoặc đổi API/UI/Docker/VM.

Các file triển khai chính: `ml_data/cohort.py` (xuất CV/evidence), `ml_data/pretraining.py` (chuẩn bị và kiểm tra điều kiện), `ml_data/requirements_logic.py` (clause evidence), cùng thay đổi ở `ingest.py`, `splitting.py`, `sampling.py`, `extraction.py`, `label_rules.py`, `annotation.py`, `__main__.py`. Assets ở `ml_data_assets/independent_cv_v3/`; test mới ở `tests/ml/test_pretraining.py`; báo cáo này sinh bằng `scripts/report-pretraining.py`. Kết quả 64 test và phạm vi lint xem [TESTING.md](../../TESTING.md).

```powershell
Set-Location D:\\JobApply
python -m ml_data check-pretraining --artifact .\\ml_data_runs\\20261114_pretraining_v3_01
if ($LASTEXITCODE -ne 0) {{ throw 'Pretraining checks failed' }}

$prepOut = '.\\ml_data_runs\\pretraining_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data prepare-experiment --upstream-run .\\ml_data_runs\\20261113_upstream_v2_01 --audited-run .\\ml_data_runs\\20261114_benchmark_audit_02 --reference-run .\\ml_data_runs\\20261113_benchmark_v2\\run_08 --prior-cv-batch .\\ml_data_runs\\20261113_cv_expansion_v1\\synthetic_cvs --assets .\\ml_data_assets\\independent_cv_v3 --output $prepOut
if ($LASTEXITCODE -ne 0) {{ throw 'Data preparation failed' }}
python -m ml_data check-pretraining --artifact $prepOut
```

Lệnh chỉ chuẩn bị/kiểm tra dữ liệu. **Dừng ở đây để trao đổi trước Bước 4**; chưa tải encoder mới, tính điểm hay train.
"""
    (folder / "pretraining_handoff.md").write_text(text, encoding="utf-8", newline="\n")
    return folder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.first, args.second, args.output))
