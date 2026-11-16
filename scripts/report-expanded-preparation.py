"""Generate the expanded cohort handoff from checked runs; never copy headline counts by hand."""
import argparse
from collections import Counter
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import (ROOT, csv_rows, file_hash, fresh_folder, read_json, require, verify, write_csv, write_json)  # noqa: E402
from ml_data.expanded_labels import check_labels  # noqa: E402
from ml_data.intake import check_intake  # noqa: E402


def identical(first, second):
    maps = [{p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*") if p.is_file()} for base in (first, second)]
    require(maps[0] == maps[1], f"Repeat differs: {first} vs {second}")
    return dict(files_identical=len(maps[0]), manifest_sha256=file_hash(first / "manifest.json"))


def report(first, second, labels_first, labels_second, tests_log, output):
    first, second, labels_first, labels_second = [Path(p) for p in (first, second, labels_first, labels_second)]
    intake_checks = [check_intake(p) for p in (first, second)]
    label_checks = [check_labels(p, labels_path) for p, labels_path in ((first, labels_first), (second, labels_second))]
    repeat = dict(intake=identical(first, second), labels=identical(labels_first, labels_second))
    # Match preserved inputs against the earlier cleanup receipt, not newly invented hashes.
    old = read_json(ROOT / "docs/ml/reports/20261116-retired-200-cv-cleanup.json")
    require(all(file_hash(ROOT / p) == h for p, h in old["protected_input_hashes"].items()), "Original source/pilot changed")
    for path, sha in old["preserved_manifests"].items():
        require(file_hash(ROOT / "ml_data_runs" / path / "manifest.json") == sha, "Historical manifest changed")
        verify(ROOT / "ml_data_runs" / path)
    require(all(not (ROOT / item["path"]).exists() for item in old["retired_directories"]), "Retired v5 data reappeared")
    log = Path(tests_log).read_text(encoding="utf-16" if Path(tests_log).read_bytes().startswith(b"\xff\xfe") else "utf-8-sig")
    result = re.search(r"Ran (\d+) tests in ([\d.]+)s\s+OK\s*$", log)
    require(result is not None, "Test log lacks a successful complete unittest result")
    tests = dict(passed=int(result[1]), seconds=float(result[2]), log_sha256=file_hash(tests_log),
                 command="python -m unittest discover -s tests/ml -v", real_dataset_trained=False)
    summary = read_json(first / "summary.json")
    distributions = read_json(first / "distributions.json")
    labels = read_json(labels_first / "summary.json")
    parsing = read_json(labels_first / "parsing_coverage.json")
    evidence = read_json(first / "authored/evidence.json") + read_json(first / "prior/evidence.json")
    folder = fresh_folder(output, tuple(p.resolve() for p in (first, second, labels_first, labels_second)))
    receipt = dict(intake=summary, distributions=distributions, labeling=labels, parsing=parsing,
        reproducibility=repeat, verification=dict(intakes=intake_checks, labels=label_checks, protected_files=len(old["protected_input_hashes"]),
        preserved_manifests=len(old["preserved_manifests"]), retired_v5_still_absent=True), tests=tests,
        evidence=dict(skill_assertions=sum(len(e["skills"]) for e in evidence), duration_assertions=sum(len(e["durations"]) for e in evidence)),
        runs=dict(intake=first.as_posix(), intake_repeat=second.as_posix(), labels=labels_first.as_posix(), labels_repeat=labels_second.as_posix()))
    write_json(folder / "20261116-expanded-preparation.json", receipt)
    config = read_json(first / "cv_import_config.json")
    for spec in config["sources"] + config["historical_cv_sources"]:
        spec["path"] = Path(os.path.relpath((first / spec["path"]).resolve(), ROOT / "docs/ml/data_configs")).as_posix()
    write_json(folder / "authored_cv_v7_import.json", config)
    # ID-only actionable backlog; no original JD prose or personal information copied into Git reports.
    facts = read_json(labels_first / "jd_facts.json")
    _, pairs = csv_rows(labels_first / "labels.csv")
    missing = Counter(p["jd_id"] for p in pairs if not p["relevance_0_1_2"])
    backlog = [dict(jd_id=jid, role=f["role"], role_precision=f["role_precision"],
        benchmark_scope=f["benchmark_scope"], unlabeled_pairs=missing[jid],
        unresolved_technical_clauses=sum(c["state"] == "unresolved" for c in f["clauses"]),
        unresolved_duration_clauses=len(f["unresolved_durations"]), parsed_duration_clauses=len(f["durations"]),
        exposure="known_jd_parser_development") for jid, f in sorted(facts.items())]
    write_csv(folder / "20261116-jd-evidence-backlog.csv", backlog, tuple(backlog[0]))
    parts = ("train", "validation", "test")
    split_table = "\n".join(f"| {p} | {distributions[p]['count']} | {distributions[p]['groups']} | {', '.join(distributions[p]['banks'])} |" for p in parts)
    label_table = "\n".join(f"| {p} | {labels['partitions'][p]['total']:,} | " + " | ".join(
        str(labels["partitions"][p]["labels"].get(k, 0)) for k in ("0", "1", "2", "unlabeled")) + " |" for p in parts)
    kind_table = "\n".join(f"| {kind} | " + " | ".join(str(distributions[p]["experience_kinds"].get(kind, 0)) for p in parts) + " |"
        for kind in ("employment", "contract", "internship", "project", "unknown"))
    labeled = sum(v for k, v in labels["labels"].items() if k != "unlabeled")
    ps_first, ps_labels = [str(p).replace("/", "\\") for p in (first, labels_first)]
    doc = f"""# Chuẩn bị mở rộng CV và nhãn — 16/11/2026

**Đã ghép {summary['cv_count']} CV synthetic / {summary['cv_groups']} ngân hàng với toàn bộ {summary['shared_jd_count']} JD, tạo và xử lý {labels['pair_count']:,} cặp. Chưa đủ điều kiện huấn luyện hoặc đánh giá xếp hạng toàn catalog.** Không chạy model mới; kết quả Bước 4 trên 50 JD vẫn là kết quả lịch sử, không áp dụng cho lô này.

Đọc [receipt sinh từ run](reports/20261116-expanded-preparation.json), [ngân hàng CV mới](../../ml_data_assets/authored_cv_v7/AUTHORING.md), [config CV](data_configs/authored_cv_v7_import.json), [backlog JD theo ID](reports/20261116-jd-evidence-backlog.csv). Báo cáo được sinh bằng `scripts/report-expanded-preparation.py` sau khi kiểm cả bốn run, không suy dữ liệu từ các số tổng hợp cũ.

## Phần đã thực hiện

Viết riêng {summary['new_cv_count']} CV mới thuộc chín ngân hàng và giữ nguyên {summary['preserved_cv_count']} CV v6. Mỗi hồ sơ mới lưu toàn văn, is_synthetic, source_group, template_group, generation_version, scenario_id, variant_history và câu bằng chứng. Không có renderer ghép câu; `profiles.json` chỉ đóng gói các bản ghi đã viết. Cả 30 CV v6 giữ nguyên ID/namespace, văn bản, metadata, lineage và partition. Chỉ phân bổ nhóm mới, seed 20261116 không thử lại. Không khôi phục lô v5 đã xóa.

Đã kiểm {receipt['evidence']['skill_assertions']} khẳng định kỹ năng, {receipt['evidence']['duration_assertions']} khẳng định thời lượng theo văn bản và offset. Unknown giữ `{{}}`. Tháng nghề nghiệp, công nghệ, thực tập và dự án không thay thế nhau. Metadata là khẳng định của tác giả synthetic, không phải gold.

| Partition | CV | Nhóm | Ngân hàng |
|---|---:|---:|---|
{split_table}

Mười nghề đều có 6 CV/train và 3 CV/validation, test: Backend Python, Backend Java, Frontend, DevOps/Cloud, QA/Testing, Backend .NET, Fullstack, Mobile, Data Engineer, AI/ML Engineer. Đây là số thực tế sau chia nhóm, không ép tỷ lệ 60/20/20 bằng cách tách ngân hàng.

| Loại kinh nghiệm | Train | Validation | Test |
|---|---:|---:|---:|
{kind_table}

{summary['cv_development']} CV nối về development lịch sử, {summary['cv_excluded']} CV bị loại theo kiểm tra khai báo. Đã so {summary['lexical']['historical_pairs']:,} cặp với {summary['lexical']['historical_cv_count']} CV lịch sử còn giữ; Jaccard từ vựng tối đa {summary['lexical']['maximum_historical_jaccard']:.6f}; giữa ngân hàng {summary['lexical']['maximum_cross_bank_jaccard']:.6f}; {summary['lexical']['repeated_long_sentences_across_banks']} câu dài lặp nguyên văn. **Những phép đo này không chứng nhận độc lập ngữ nghĩa.** CV cùng một tác giả AI, đa số là hồ sơ ngắn có cách trình bày tương tự, chưa đại diện CV thật nhiều trang hoặc nguồn tác giả đa dạng. Khác ngân hàng cũng gây khác biệt miền nội dung.

Protocol **known-JD**: tất cả {summary['shared_jd_count']} JD / {summary['jd_groups']} nhóm được dùng chung. JD unknown, generic và ngoài phạm vi vẫn ở catalog; không lén loại để tăng điểm. Giữ exposure parser-development và quan hệ với benchmark cũ; không tuyên bố đánh giá trên JD chưa từng thấy. Không nhập dữ liệu lịch sử vào database app.

## Bộ luật và kết quả nhãn thực tế

Phiên bản `expanded-technical-proxy-v1` dùng luật cố định trên mọi partition, không đọc ranking. Luật cũ vẫn bị chặn khi gặp taxonomy v4; CLI mới xử lý riêng, không sửa nhãn lịch sử.

- **0:** chỉ khi có phủ định kỹ năng rõ ràng trong CV mâu thuẫn với yêu cầu bắt buộc đã phân tích đầy đủ, hoặc thời lượng cùng scope nghề nghiệp thấp hơn ngưỡng bắt buộc rõ ràng.
- **1:** cùng nghề/chức năng có thể chồng lấn và có công nghệ được nêu tích cực ở cả hai phía; còn điều kiện chưa xác định nên chỉ nói tương thích kỹ thuật một phần.
- **2:** cùng nghề, mọi điều kiện kỹ thuật quan sát được đã phân tích và đáp ứng, có ngưỡng thời lượng rõ cùng scope được đáp ứng. Không khẳng định đáp ứng học vấn/ngoại ngữ/tất cả điều kiện tuyển dụng.
- **Trống:** không đủ căn cứ. Khác tên nghề, không nhắc công nghệ, hard candidate, thiếu metadata đều không tự trở thành 0. Ưu tiên không phải bắt buộc; AND/OR, phạm vi điều kiện và câu chưa phân tích được không tự suy diễn.

| Partition | Cặp xử lý | Nhãn 0 | Nhãn 1 | Nhãn 2 | Chưa nhãn |
|---|---:|---:|---:|---:|---:|
{label_table}

Tổng có **{labeled:,} cặp mang nhãn proxy ({100*labeled/labels['pair_count']:.2f}%)**, **{labels['labels'].get('unlabeled', 0):,} cặp còn trống**. Train lấy {summary['candidate_selection'].get('uniform_random_without_replacement', 0)} random và {summary['train_candidate_pairs']-summary['candidate_selection'].get('uniform_random_without_replacement', 0)} hard candidates, có {summary['sampling_shortages']} lượt thiếu quota; không tạo bù. Validation/test đã tạo đủ lưới CV × 788 JD, nhưng **đủ cặp không có nghĩa đủ nhãn**.

Giới hạn của parser mới là rõ rệt: chỉ {parsing['jd_with_mandatory_technology']} JD có câu công nghệ bắt buộc thuộc ngữ pháp đầy đủ đang hỗ trợ, {parsing['jd_with_parsed_duration']} JD có ngưỡng thời lượng đơn giản đủ rõ theo parser này; {parsing['jd_with_unresolved_duration']} JD có câu thời lượng chưa phân tích chắc chắn. Có {parsing['clause_states'].get('unresolved', 0)} mệnh đề công nghệ unresolved. Đây **không** có nghĩa chỉ từng đó JD chứa yêu cầu thực tế: bộ đọc ngôn ngữ còn hẹp và dữ liệu có nhiều điều kiện chưa rõ. Metadata thời lượng v4 giữ nguyên; phiên bản nhãn mới không tự coi fallback “professional experience” là bằng chứng scope chính xác.

Train thiếu lớp {', '.join(labels['missing_train_classes'])}; {labels['cv_without_label_2']}/{summary['cv_count']} CV chưa có positive nhãn 2 theo luật này. Vì vậy **chưa train LR**, chưa chọn model, chưa tính Recall@5/NDCG@5 toàn catalog và không biến nhãn trống thành 0. Không dùng tỷ lệ kiểm tra schema hợp lệ để tuyên bố nhãn đúng 100%.

## Kiểm chứng và nơi mở dữ liệu

- Intake chính: `{first.as_posix()}`; lặp: `{second.as_posix()}` — **{repeat['intake']['files_identical']} file giống byte**, gồm manifest.
- Nhãn chính: `{labels_first.as_posix()}`; lặp: `{labels_second.as_posix()}` — **{repeat['labels']['files_identical']} file giống byte**, gồm manifest.
- **{tests['passed']} test đạt**, {tests['seconds']:.3f} giây; kiểm scope, AND/OR, optional, mâu thuẫn rõ, giữ lineage/partition, lưới census và chặn metric khi nhãn thiếu. Test dùng fixture riêng; không huấn luyện catalog thực.
- Xác minh 3 CSV nguồn + 51 file pilot và {len(old['preserved_manifests'])} run lịch sử theo receipt trước đó không đổi. Tám thư mục v5 vẫn không tồn tại. Không commit dữ liệu nguồn lớn, không đổi API/UI/Docker/VM, chưa commit/push.

Trong intake: `authored/cvs.csv` là 90 CV mới; `prior/cvs.csv` là 30 CV giữ nguyên; `records.jsonl` ghép {summary['cv_count']+summary['shared_jd_count']} record; `assignments.jsonl`, `distributions.json`, `leakage_report.json` cho biết split thực tế. `cv_import_config.json` và snapshot giữ namespace riêng của từng nguồn.

Trong run nhãn: `labels.csv` để lọc theo partition/trạng thái; `evidence.jsonl` ghi quyết định từng cặp; `cv_facts.json` và `jd_facts.json` lưu câu trích/offset, scope, toán tử và các phần chưa phân tích. `policy.json`, `parsing_coverage.json`, `summary.json`, `manifest.json` ghi luật, độ phủ, hash. Không có model mới trong các thư mục này.

```powershell
Set-Location D:\\JobApply
$pythonML = '.\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe'
& $pythonML -m ml_data check-cv-intake --artifact '.\\{ps_first}'
if ($LASTEXITCODE -ne 0) {{ throw 'CV intake check failed' }}
& $pythonML -m ml_data check-expanded-labels --intake '.\\{ps_first}' --artifact '.\\{ps_labels}'
if ($LASTEXITCODE -ne 0) {{ throw 'Proxy label check failed' }}

Import-Csv '.\\{ps_labels}\\labels.csv' | Group-Object partition,label_status,relevance_0_1_2 | Select-Object Count,Name

$runStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$cvOut = '.\\ml_data_runs\\cv_expanded_' + $runStamp
$labelOut = '.\\ml_data_runs\\labels_expanded_' + $runStamp
& $pythonML -m ml_data prepare-cv-intake --metadata-run .\\ml_data_runs\\20261116_jd_metadata_v4_03 --catalogue-run .\\ml_data_runs\\20261116_jd_catalogue_v1_01 --preparation-run .\\ml_data_runs\\20261114_pretraining_v3_01 --assets .\\ml_data_assets\\authored_cv_v7 --prior-intake .\\ml_data_runs\\20261116_authored_cv_v6_02 --output $cvOut
if ($LASTEXITCODE -ne 0) {{ throw 'Expanded CV import failed' }}
& $pythonML -m ml_data prepare-expanded-labels --intake $cvOut --output $labelOut
if ($LASTEXITCODE -ne 0) {{ throw 'Expanded labeling failed' }}
```

## Điều kiện còn thiếu trước huấn luyện — chưa thực hiện

1. Mở rộng parser điều kiện trên **JD đã thuộc development** bằng fixture riêng: câu thời lượng có scope nghề/công nghệ, danh sách AND/OR, điều kiện nhiều cấp độ, phủ định và ưu tiên. Cần báo cả phần không hiểu; không thay “không rõ” bằng “không đạt”. Backlog ID phía trên cho biết mệnh đề nào đang thiếu khả năng phân tích; câu gốc ở run local. Phiên bản hiện tại chỉ là chính sách proxy bảo thủ có test, chưa hoàn thành độ phủ nhãn cần cho thí nghiệm.
2. Bổ sung bằng chứng cho các quyết định tương thích/không tương thích còn thiếu, kiểm đủ lớp ở train và positive ở từng nhóm đánh giá. Không sửa CV để khớp JD đích hoặc tự nâng nhãn. Nếu sửa luật/features dựa vào kết quả của nhóm validation/test hiện tại, nhóm đó phải chuyển development; không đổi seed/lineage để gọi lại là test mới.
3. Chỉ huấn luyện sau khi khóa phiên bản dữ liệu, luật và phạm vi đánh giá. Nếu chọn đánh giá trên tập con có nhãn, phải công bố phạm vi và thiên lệch chọn mẫu; không gọi đó là Recall/NDCG trên toàn 788 JD. Nhãn do luật tạo vẫn chỉ đo khả năng học/đồng thuận với luật, chưa xác nhận phù hợp tuyển dụng thật.
4. Data Analyst vẫn là mục tiêu: kho hiện tại chưa bổ sung được JD mới đủ điều kiện ngoài development cho positive benchmark. Cần JD có nhiệm vụ phân tích, điều kiện và provenance rõ; không thay Data Analyst bằng Data Engineer để báo đủ nghề. Muốn kết luận trên ứng viên thật còn cần nguồn CV được phép sử dụng và bằng chứng đánh giá ngoài bộ luật, không bắt buộc vòng hai reviewer.

Không tăng số CV đơn thuần để che thiếu nhãn. Lượt này hoàn thành công cụ tiếp nhận, chia nhóm, xử lý cặp, kiểm chứng và báo cáo; **điều kiện sẵn sàng huấn luyện vẫn chưa đạt**, được lưu rõ thay vì tuyên bố hoàn tất giả.
"""
    (folder / "expanded_preparation.md").write_text(doc, encoding="utf-8", newline="\n")
    print(dict(reproducibility=repeat, tests=tests, ready_for_training=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "labels-first", "labels-second", "tests-log", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report(args.first, args.second, args.labels_first, args.labels_second, args.tests_log, args.output)
