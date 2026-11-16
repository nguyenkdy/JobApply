"""Aggregate a checked small authored-CV intake, without certifying ML quality."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, write_json, require  # noqa: E402
from ml_data.intake import check_intake  # noqa: E402


def report(first, second, output):
    first, second = Path(first), Path(second)
    for p in (first, second):
        check_intake(p)
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], "Intake runs differ")
    summary = read_json(first / "summary.json")
    distributions = read_json(first / "distributions.json")
    evidence = read_json(first / "authored/evidence.json")
    folder = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(summary=summary, distributions=distributions,
        evidence=dict(skill_assertions=sum(len(e["skills"]) for e in evidence), duration_assertions=sum(len(e["durations"]) for e in evidence)),
        reproducibility=dict(files_identical=len(maps[0]), manifest_sha256=file_hash(first / "manifest.json")))
    write_json(folder / "20261116-authored-cv-intake.json", receipt)
    config = read_json(first / "cv_import_config.json")
    for spec in config["sources"] + config["historical_cv_sources"]:
        spec["path"] = Path(os.path.relpath((first / spec["path"]).resolve(), ROOT / "docs/ml/data_configs")).as_posix()
    write_json(folder / "authored_cv_v6_import.json", config)
    split = "\n".join(f"| {part} | {distributions[part]['count']} | {distributions[part]['groups']} | {', '.join(distributions[part]['banks'])} |"
                      for part in ("train", "validation", "test"))
    kinds = "\n".join(f"| {kind} | " + " | ".join(str(distributions[p]["experience_kinds"].get(kind, 0)) for p in ("train", "validation", "test")) + " |"
                      for kind in ("employment", "contract", "internship", "project", "unknown"))
    doc = f"""# Tiếp nhận CV viết riêng v6 — 16/11/2026

**Đã tạo và nhập {summary['cv_count']} CV synthetic mới, 10 nghề, chia theo ba ngân hàng kịch bản nguồn; preview dùng toàn bộ {summary['shared_jd_count']} JD.** Đây là lô nhỏ kiểm tra quy trình trước khi mở rộng, chưa phải bộ dữ liệu đủ để chọn model hoặc kết luận ML hoạt động tốt.

[Receipt từ run thực](reports/20261116-authored-cv-intake.json), [quy trình tác giả hóa](../../ml_data_assets/authored_cv_v6/AUTHORING.md), [config nhập phần CV](data_configs/authored_cv_v6_import.json).

## Nguồn mới và giới hạn

Mỗi hồ sơ được viết nguyên văn riêng trong `profiles.json`, không có chương trình tạo nội dung bằng slot hoặc lắp câu mẫu. Công cụ chỉ vận chuyển văn bản và kiểm bằng chứng. Không lấy lại generator hoặc nội dung lô 200 CV v5 đã xóa; không có JD đích, ranking hoặc nhãn mong muốn trong đầu vào tác giả hóa.

Ba ngân hàng là nghiên cứu/phòng thí nghiệm, sản xuất sáng tạo và dịch vụ công ích. Mỗi ngân hàng có đủ Backend Python, Backend Java, Frontend, DevOps/Cloud, QA/Testing, Backend .NET, Fullstack, Mobile, Data Engineer, AI/ML Engineer. `template_group` được dùng như khóa gom cả ngân hàng một cách bảo thủ; không tuyên bố đây là ba tác giả hoặc ba nguồn ứng viên thật độc lập. Tất cả hồ sơ vẫn có cùng tác giả AI/cohort, cùng ngôn ngữ và có thể có thiên lệch chung.

Đã kiểm {receipt['evidence']['skill_assertions']} khẳng định kỹ năng và {receipt['evidence']['duration_assertions']} khẳng định thời lượng khớp câu gốc/offset. Thời gian nghề nghiệp, công nghệ, thực tập và dự án có scope riêng; unknown là `{{}}`. Metadata vẫn là khẳng định tác giả synthetic, không phải gold hoặc đánh giá độc lập.

Đã đối chiếu từ vựng với {summary['lexical']['historical_cv_count']} CV lịch sử còn giữ ({summary['lexical']['historical_pairs']} cặp so sánh). Jaccard 3-token cao nhất với lịch sử là {summary['lexical']['maximum_historical_jaccard']:.6f}; giữa các ngân hàng mới là {summary['lexical']['maximum_cross_bank_jaccard']:.6f}. Có {summary['lexical']['repeated_long_sentences_across_banks']} câu dài ít nhất 12 từ lặp nguyên văn giữa ngân hàng. Các phép đo này **không chứng minh độc lập ngữ nghĩa**, không phát hiện được mọi paraphrase hoặc nguồn tác giả bị khai sai. Vì v5 đã xóa, không tuyên bố đã đối chiếu nguyên văn với lô đó.

Theo các kiểm tra hiện có, {summary['cv_development']} CV mới nối về development lịch sử, {summary['cv_excluded']} CV bị loại/cách ly. Chỉ được coi đây là kết quả kỹ thuật trên provenance đã khai báo.

## Preview giữ nguyên nhóm

| Partition | CV | Nhóm nguồn | Ngân hàng |
|---|---:|---:|---|
{split}

Mỗi tập có một CV cho mỗi nghề, và phân bố trải nghiệm dưới đây:

| Loại trải nghiệm | Train | Validation | Test |
|---|---:|---:|---:|
{kinds}

Seed `20261116`, không thử lại seed. Dùng allocator hiện có, giữ nguyên nhóm; ba nhóm phải dành một nhóm cho mỗi tập nên tỷ lệ thực tế 10/10/10 khác đề xuất 60/20/20. Giữ group/source/ancestor/near links; không xóa ancestry để đạt tỷ lệ.

Protocol là **known-JD**: toàn catalog 788 JD dùng chung, vẫn thuộc 698 nhóm nguồn/trùng/gần trùng. Giữ các JD unknown/generic/ngoài phạm vi và overlay đã dùng phát triển parser; không gọi đây là holdout JD mới. Một ngân hàng nội dung khác nhau trong mỗi tập làm khác biệt miền nội dung bị trộn với hiệu ứng holdout. Với một CV/nghề/tập và một ngân hàng/tập, **chưa đủ để chọn model hoặc báo chất lượng đáng tin theo nghề**.

## Cặp chuẩn bị và chính sách nhãn

Đã tạo **{summary['train_candidate_pairs']} cặp ứng viên train**, gồm {summary['candidate_selection'].get('uniform_random_without_replacement', 0)} random và {summary['train_candidate_pairs']-summary['candidate_selection'].get('uniform_random_without_replacement', 0)} hard candidates. Có {summary['sampling_shortages']} lượt thiếu ứng viên theo quota; giữ nguyên số thực tế, không bịa hoặc gán 0 để lấp. Tất cả `label_status=unlabeled`, ô relevance rỗng.

Validation/test lần lượt dự kiến **{summary['evaluation_pair_workload']['validation']:,}/{summary['evaluation_pair_workload']['test']:,} cặp** nếu đánh giá toàn catalog; chưa tạo lưới hai tập này. Quan hệ nghề được ghi dưới dạng chẩn đoán: cùng nghề, có thể chồng lấn chức năng, khác tên nhưng chưa kết luận fit, hoặc unknown/generic. Backend–Fullstack không tự thành nhãn 0. Chốt chặn nhãn trên taxonomy mở rộng vẫn còn; đây chưa phải rubric hoàn chỉnh 0/1/2.

`structural_partition_ready=true` chỉ nói chia nhóm đúng chính sách khai báo. `final_test_ready=false`, nhãn mới bằng 0, model mới bằng 0. Không chạy lại pilot để tăng điểm và không đổi kết quả Bước 4.

## Artifact và kiểm chứng

Run chính: `{first.as_posix()}`; run đối chiếu: `{second.as_posix()}`. Hai run có **{len(maps[0])}/{len(maps[0])} file giống byte**. Ba CSV nguồn, 51 file pilot và các run đầu vào được xác minh không đổi. Lô v5 đã xóa không được khôi phục.

- `authored/cvs.csv`, `evidence.json`, `profiles.json`, `design.json`, `AUTHORING.md`: văn bản, schema, bằng chứng và khai báo nguồn.
- `cv_dataset/`: snapshots, nhóm, liên kết và protected history.
- `catalogue/`: nguyên trạng bản metadata JD v4 và overlay exposure.
- `records.jsonl`: {summary['cv_count']+summary['shared_jd_count']} record kết hợp; `assignments.jsonl`, `leakage_report.json`, `distributions.json`: preview.
- `train_candidates/pairs.csv`, `selection.json`, `shortages.json`: cặp chưa nhãn và lý do lấy mẫu.
- `lexical_diagnostics.json`: kết quả so trùng có giới hạn rõ.

[Kiểm thử mã nguồn](../../TESTING.md). Công cụ mới: `ml_data/intake.py`, CLI `prepare-cv-intake`/`check-cv-intake`, `scripts/report-cv-intake.py`, `tests/ml/test_intake.py`. Không đổi API/UI/Docker/VM và chưa commit.

```powershell
Set-Location D:\\JobApply
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data check-cv-intake --artifact .\\{first.as_posix().replace('/', chr(92))}
if ($LASTEXITCODE -ne 0) {{ throw 'CV intake check failed' }}

$intakeOut = '.\\ml_data_runs\\cv_intake_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data prepare-cv-intake --metadata-run .\\ml_data_runs\\20261116_jd_metadata_v4_03 --catalogue-run .\\ml_data_runs\\20261116_jd_catalogue_v1_01 --preparation-run .\\ml_data_runs\\20261114_pretraining_v3_01 --output $intakeOut
if ($LASTEXITCODE -ne 0) {{ throw 'CV intake failed' }}
```

## Bước tiếp theo — chưa thực hiện

Mở rộng số ngân hàng nguồn trước số lượng biến thể: một đích thiết kế tiếp theo là ít nhất 12 ngân hàng × 10 nghề = 120 CV viết riêng, cần thêm 90 CV với nguồn kịch bản mới. Đây là đề xuất, chưa phải dữ liệu hiện có. Giữ ngân hàng cũ/ancestry khi có biến thể; không đổi tên ngân hàng để tăng số nhóm. Cần nhiều ngân hàng trong mỗi partition, theo dõi thiên lệch miền và vẫn công bố giới hạn tác giả AI chung.

Sau khi đủ độ phủ, khóa phiên bản split, định nghĩa rubric theo nhiệm vụ/điều kiện bắt buộc/ưu tiên và scope kinh nghiệm rồi kiểm độ phủ nhãn trên toàn catalog. JD thiếu bằng chứng vẫn được để chưa nhãn. Data Analyst vẫn là mục tiêu nghiên cứu nhưng cần JD hợp lệ ngoài development trước khi thêm positive benchmark. Chưa train hoặc chốt model từ lô nhỏ này.
"""
    (folder / "authored_cv_intake.md").write_text(doc, encoding="utf-8", newline="\n")
    print(f"Verified {len(maps[0])} identical files; wrote intake handoff")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report(args.first, args.second, args.output)
