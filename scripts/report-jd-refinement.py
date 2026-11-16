"""Generate public aggregate handoff from two verified local metadata artifacts."""
import argparse
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import file_hash, fresh_folder, read_json, require, verify, write_json  # noqa: E402


def report(first, second, output):
    first, second = Path(first), Path(second)
    for run in (first, second):
        verify(run, "jd-metadata-refinement")
    maps = [{p.relative_to(run).as_posix(): file_hash(p) for p in run.rglob("*") if p.is_file()}
            for run in (first, second)]
    require(maps[0] == maps[1], "Repeated metadata runs differ")
    summary, plan = read_json(first / "summary.json"), read_json(first / "cv_design_plan.json")
    folder = fresh_folder(output, (first.resolve(), second.resolve()))
    receipt = dict(summary=summary, cv_plan=plan,
                   reproducibility=dict(identical_files=len(maps[0]), manifest_sha256=file_hash(first / "manifest.json")))
    write_json(folder / "20261116-jd-metadata-v4.json", receipt)
    shutil.copyfile(first / "role_coverage.csv", folder / "20261116-jd-metadata-role-coverage.csv")
    missing = "\n".join(f"| {name} | {summary['missing_before'][field]} | {summary['missing_after'][field]} |"
                        for field, name in (("role", "Nghề"), ("skills", "Kỹ năng"), ("stack", "Stack"), ("experience", "Thời lượng theo scope")))
    role_plan = "\n".join(f"| {r['role']} | {r['jd_count']} | {r['jd_groups']} | {r['proposed_cvs']} |" for r in plan["roles"])
    body = f"""# Metadata catalog mở rộng và thiết kế CV — 16/11/2026

Đã chạy bộ bổ sung metadata `{summary['version']}` trên **{summary['jd_count']} JD / {summary['groups']} nhóm**. Giữ đủ catalog, không sửa nguồn, ID, văn bản, nhóm, quality gate hoặc run cũ. Không tự nối lại bản cách ly để tăng số lượng.

[Receipt và kế hoạch máy đọc](reports/20261116-jd-metadata-v4.json), [phân bố nghề mới](reports/20261116-jd-metadata-role-coverage.csv), [nguồn catalog trước bổ sung](jd_catalogue_expansion.md).

## Đã thực hiện

| Metadata còn thiếu | Trước | Sau |
|---|---:|---:|
{missing}

{summary['changed_records']} JD có thay đổi metadata; {summary['fields_changed']['role']} thay đổi nghề, {summary['fields_changed']['skills']} thay đổi kỹ năng, {summary['fields_changed']['stack']} thay đổi stack. Các số này chồng nhau. Có cả sửa phân loại cũ (Fullstack từng bị xếp Frontend/Backend, quản lý từng bị gộp Business Analyst), không chỉ lấp ô trống.

Nghề được lưu ở ba mức: {summary['role_precision'].get('occupation_rule', 0)} theo quy tắc nghề, {summary['role_precision'].get('generic', 0)} chỉ biết Backend chưa rõ stack, {summary['role_precision'].get('unknown_or_conflicting', 0)} unknown hoặc xung đột. Nhãn generic không chứng minh cùng nghề cụ thể; khác chuỗi tên nghề không đủ kết luận không phù hợp.

Có **{summary['benchmark_scope'].get('outside_software_benchmark', 0)} JD được quy tắc đánh dấu ngoài phạm vi benchmark phần mềm** (CNC/CAM, tự động hóa công nghiệp, giáo dục, kinh doanh, marketing, vật liệu). Chúng vẫn ở catalog 788; cần báo riêng nếu thiết kế benchmark giới hạn nghề. Không âm thầm đổi mẫu số thành một catalog nhỏ hơn.

Bổ sung từ vựng công nghệ cho mobile, dữ liệu, AI và các stack còn thiếu; lưu field, offset, nguyên văn evidence và phiên bản. Phân biệt thuật ngữ ưu tiên/không bắt buộc với core mention; ngay cả core mention cũng không chứng minh yêu cầu bắt buộc. Đã đối chiếu **{summary['evidence_audit']['literal_spans_verified']} đoạn evidence**. Đây là độ phủ và tính khớp nguyên văn, **không phải điểm accuracy trên dữ liệu độc lập**.

Thời lượng kinh nghiệm không đổi: {summary['missing_after']['experience']} JD còn thiếu. Trong số đó, {summary['missing_reasons'].get('no_numeric_duration_in_requirements', 0)} không có dạng thời lượng số được nhận diện trong requirements, {summary['missing_reasons'].get('numeric_duration_without_supported_scope_or_minimum', 0)} có số nhưng chưa xác định được scope/cận yêu cầu bằng quy tắc hiện tại. Không lấy số năm từ chức danh senior hoặc gán số tháng cho từng công nghệ.

Đã thêm chốt chặn ở `label_rules.py`: dữ liệu có `label_policy_status=requires_expanded_taxonomy_policy` trả `insufficient_evidence`, ô nhãn rỗng. Bộ luật cũ chưa được phép gán 0 cho Backend Java so với Fullstack chỉ vì khác tên. Chưa tạo nhãn CV–JD mới.

## Lịch sử dùng dữ liệu và artifact

Run hiện hành: `{first.as_posix()}`. `records.jsonl` và `canonical_jd_enriched.csv` chứa 788 JD với metadata mới; `jd_extraction_evidence.json` chứa bằng chứng; `metadata_changes.jsonl` ghi trước/sau và lý do còn thiếu. Snapshot trước sửa và các file nhóm/ID được giữ trong run.

Catalog đã được dùng phát triển bộ trích xuất. `metadata_use_exposure=development` và `exposure_overlay.json` đánh dấu toàn bộ các nhóm liên quan, kể cả record cùng nhóm nằm ngoài catalog. Cờ exposure lịch sử được giữ nguyên để truy vết. **Không dùng catalog này làm holdout JD mới**; vẫn có thể dùng làm kho JD đã biết trong protocol known-JD với CV mới chưa dùng chỉnh phương pháp.

Artifact mang loại `jd-metadata-refinement`, chưa phải dataset huấn luyện/split hoàn tất. Công cụ phải áp dụng overlay và chính sách taxonomy khi nhập tiếp; không bỏ các trường này để chạy luật cũ. 60 CV đã dùng ở Bước 4 tiếp tục là hồi quy.

## Thiết kế lô CV tiếp theo — chưa tạo CV

Đề xuất **{plan['proposed_cv_count']} CV synthetic mới**, 20 mỗi nghề dưới đây; bổ sung Fullstack theo phân bố thực tế. Đây là lô đầu để mở rộng độ phủ, chưa phủ mọi nghề trong kho; các nghề còn lại được liệt kê trong `cv_design_plan.json`, không bị loại khỏi mục tiêu.

| Nghề | JD hiện có | Nhóm JD | CV dự kiến |
|---|---:|---:|---:|
{role_plan}

Data Analyst vẫn thuộc mục tiêu nghiên cứu; nguồn trước đó không có JD ngoài development qua gate cho nhóm này. Cần phục hồi/bổ sung JD hợp lệ trước khi tuyên bố có benchmark positive cho Data Analyst. Các JD generic/unknown không được tự coi là Data Analyst.

Dự kiến 10 họ khung viết thực sự, mỗi họ hai CV cho mỗi nghề; từng kịch bản nguồn phải mới, độc lập với JD đích và ranking. Chia theo họ có thể cho **120/40/40 CV** (train/validation/test) nếu kiểm tra lineage/gần trùng không nối các họ lại. Đây là dự kiến, chưa phải split đã đạt. Không sửa mã họ để ép tỷ lệ.

Phủ employment, contract, internship, project và unknown. Không đổi thời gian dự án/thực tập thành thời gian làm nghề. Mọi skill/thời lượng phải có câu bằng chứng trong CV; không có danh tính thật; `is_synthetic=true`.

Schema CSV: `cv_id, cv_text, source_group, template_group, is_synthetic, role, skills, stack, experience_json, exposure, text_scope, lineage_json`. Skills/stack phân cách `;`; experience JSON là scope → tháng, unknown là `{{}}`. Lineage giữ scenario ID, generation version/cohort, họ khung thực, parent/ancestor và variant history. Sidecar evidence giữ câu trích, offset, scope và loại trải nghiệm. [Config CV hiện có](data_configs/new_cvs.template.json).

Với toàn catalog, validation/test lần lượt dự kiến **{plan['validation_pairs']:,} / {plan['test_pairs']:,} cặp**. Train lấy 10 random và tối đa 3 hard candidates mỗi loại role/stack/experience cho mỗi CV, tối đa {plan['training_sampling']['maximum_pairs']:,} trước bỏ trùng/kiểm tra khả dụng. Hard candidate chưa phải nhãn 0. Chưa sinh các cặp hoặc nhãn này.

## Kiểm chứng và PowerShell

Hai lần chạy có **{len(maps[0])}/{len(maps[0])} file giống byte**. Ba CSV nguồn và {summary['pilot_files_unchanged']} file pilot giữ nguyên hash; manifest catalog đầu vào không đổi. Kết quả Bước 4 trên 50 JD không thay đổi. [Kiểm thử mã nguồn](../../TESTING.md).

```powershell
Set-Location D:\\JobApply
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data verify --artifact .\\{first.as_posix().replace('/', chr(92))}
if ($LASTEXITCODE -ne 0) {{ throw 'Metadata verification failed' }}

$metadataOut = '.\\ml_data_runs\\jd_metadata_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data refine-jd-catalogue --catalogue-run .\\ml_data_runs\\20261116_jd_catalogue_v1_01 --output $metadataOut
if ($LASTEXITCODE -ne 0) {{ throw 'Metadata refinement failed' }}
```

**Còn phải làm:** tác giả hóa CV mới theo thiết kế, kiểm lineage và tạo preview split; xây chính sách so nghề tương thích với Fullstack/generic/các nghề mở rộng trước khi gán nhãn. Chưa train lại, chưa tích hợp app hay thay đổi API/UI/Docker/VM. Dữ liệu synthetic và nhãn nội bộ chưa chứng minh chất lượng trên ứng viên thật.
"""
    (folder / "jd_metadata_refinement.md").write_text(body, encoding="utf-8", newline="\n")
    print(f"Verified {len(maps[0])} identical files; reports written to {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report(args.first, args.second, args.output)
