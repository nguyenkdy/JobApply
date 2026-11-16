"""Publish catalogue expansion facts from two sealed, identical runs."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import ROOT, file_hash, fresh_folder, read_json, require, verify, write_csv, write_json


def build(first, second, output):
    first, second = Path(first).resolve(), Path(second).resolve()
    for path in (first, second):
        verify(path, "jd-catalogue-expansion")
    hashes = [{p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob("*") if p.is_file()} for root in (first, second)]
    require(hashes[0] == hashes[1], "Expansion runs differ")
    r = read_json(first / "summary.json")
    out = fresh_folder(output, (first, second))
    receipt = dict(r, reproducibility=dict(all_bytes_identical=True, files_identical=len(hashes[0]),
        run_paths=[p.relative_to(ROOT).as_posix() for p in (first, second)], manifest_sha256=file_hash(first / "manifest.json")))
    write_json(out / "20261116-jd-catalogue.json", receipt)
    config = read_json(first / "import_config.json")
    for item in config["sources"] + config["context_files"]:
        item["path"] = "../../../" + Path(item["path"]).relative_to(ROOT).as_posix()
    write_json(out / "all_jd_import.json", config)
    rows = [dict(role=x["role"], jd_count=x["jd_count"], jd_groups=x["jd_groups"],
                 existing_cv_count=x["existing_cv_count"], **{"missing_"+f: n for f, n in x["missing"].items()}) for x in r["workload"]["by_role"]]
    write_csv(out / "20261116-jd-role-coverage.csv", rows, tuple(rows[0]))
    role_lines = "\n".join(f"| {x['role']} | {x['jd_count']} | {x['jd_groups']} | {x['existing_cv_count']} |" for x in rows)
    d, missing, workload = r["dispositions"], r["metadata_missing"], r["workload"]
    text = f"""# Mở rộng toàn bộ catalog JD — 16/11/2026

**Đã nhập lại kho JD thành dataset riêng có version và xuất đủ {r['catalogue_count']} JD đủ gate ngoài development làm catalog mở rộng.** Đây là {r['added_jd_count']} ID ngoài catalog 50 JD trước đó, không phải thu thập {r['added_jd_count']} JD mới từ Internet. Tổng nguồn vẫn {r['source_jd_count']} JD. Ba CSV là ba giai đoạn cùng kho, chỉ matching được nhập thành record; raw/clean là snapshots đối chiếu.

[Receipt từ hai run thực](reports/20261116-jd-catalogue.json), [phân bố nghề](reports/20261116-jd-role-coverage.csv), [config nhập JD](data_configs/all_jd_import.json).

## Bao gồm và giữ riêng

| Trạng thái | JD | Sử dụng |
|---|---:|---|
| Catalog mở rộng | {d['catalogue_candidate']} | Tất cả JD keep ngoài nhóm development nguồn, không lọc nghề/metadata để làm đẹp số liệu |
| Keep development | {d['development_only']} | Dùng phát triển/hồi quy, không đưa vào catalog đánh giá mới |
| Loại trùng chính xác | {d['exclude_exact_duplicate']} | Giữ nguồn và lý do, không đưa vào catalog |
| Cách ly | {d['quarantine']} | Giữ nguyên lỗi/nguồn; chưa sửa nội dung để vượt gate |

Toàn bộ {r['original_development_related']} record thuộc các nhóm development giữ nguyên cờ, kể cả những record đã nằm trong loại/cách ly. Vì vậy 154 không cộng thêm vào các dòng của bảng trên.

Giữ ID, text gốc/chuẩn hóa, hash, nguồn, lineage, quyết định chất lượng và metadata như bản đã kiểm chứng. Không trích xuất lại hoặc thay đổi quy tắc để tăng độ phủ trong lượt này. Đã kiểm tra {r['evidence']['literal_spans_verified']} đoạn evidence/offset trên {r['evidence']['jd_count']} JD khớp nguồn; đây là kiểm chứng nguyên văn, không chứng nhận mọi suy luận nghề/thời lượng đều đúng.

## Trùng/gần trùng và lịch sử đã xem

Catalog {r['catalogue_count']} JD có **{r['catalogue_groups']} nhóm**, trong đó {r['groups_with_multiple_candidates']} nhóm có nhiều record ({r['candidate_rows_in_multi_groups']} JD). Giữ tất cả ứng viên và quan hệ nhóm; không coi mỗi record là một mẫu độc lập. Có thêm view {r['catalogue_groups']} đại diện nhóm để phục vụ kiểm tra/metric theo nhóm về sau; chưa dùng view này thay catalog đầy đủ.

50 ID đã dùng trong Bước 4 vẫn được nhận diện; có **5 JD cùng nhóm** với chúng. `completed_benchmark_exposure.json` lưu đủ 55 JD liên quan và 60 CV đã dùng trong thí nghiệm. Các CV này chỉ dùng development/regression cho vòng sau; không chia lại seed hoặc gọi chúng là final test mới. 733 JD ngoài các nhóm benchmark đã dùng chưa tự trở thành test: còn phụ thuộc protocol, metadata và CV mới.

Known-jd có thể dùng catalog chung gồm cả JD đã biết, nhưng CV đánh giá mới phải thuộc các nhóm chưa dùng chỉnh phương pháp. Nếu muốn kiểm tra JD mới, cần tách cả nhóm JD và loại toàn bộ nhóm đã tiếp xúc khỏi phần holdout đó. Chưa khóa split mới trong lượt này.

## Metadata thực tế còn thiếu

| Trường | JD thiếu / {r['catalogue_count']} |
|---|---:|
| Nghề | {missing['role']} |
| Kỹ năng | {missing['skills']} |
| Stack | {missing['stack']} |
| Kinh nghiệm có scope | {missing['experience']} |

Chỉ {r['metadata_fields_present_count']} JD có giá trị ở cả bốn trường; có giá trị vẫn chưa chứng minh đúng ngữ nghĩa. Các số thiếu chồng nhau. Tất cả vẫn có trong catalog nếu qua gate text/nguồn; unknown giữ rỗng hoặc `{{}}`, không thay bằng 0 tháng/nhãn 0.

Theo điều kiện đầu vào của bộ luật proxy hiện tại, nếu ghép 60 CV đã có với toàn catalog thì có **{workload['full_grid_pairs']:,} cặp**, trong đó **{workload['pairs_missing_minimum_proxy_metadata']:,} cặp thiếu metadata tối thiểu để kết luận**. Đây chỉ là tính khối lượng và độ phủ, chưa tạo cặp hay gán nhãn. Không được bỏ các JD thiếu nhãn rồi tuyên bố metric trên đủ {r['catalogue_count']} JD.

## Phân bố nghề và thiếu CV tương ứng

| Nghề theo bộ trích xuất hiện tại | JD | Nhóm JD | CV đã có (hồi quy) |
|---|---:|---:|---:|
{role_lines}

Ngoài bảng có **{missing['role']} JD unknown role**. Không lọc bỏ các nghề chưa có CV. Số nhóm có thể xuất hiện ở nhiều dòng nếu nhóm có nhiều vai trò; không cộng cột nhóm thành số nhóm độc lập toàn kho.

Data Analyst vẫn thuộc mục tiêu: 9 tag nguồn, 8 dấu hiệu chức danh, 4 nối pilot và 0 ngoài pilot qua gate trong kiểm kê trước. Cần khôi phục/bổ sung JD hợp lệ cho nhóm này; không dùng bốn JD development/quarantine để đủ quota benchmark.

## Artifact để dùng tiếp

Run chính: `{first.relative_to(ROOT).as_posix()}`.

- `dataset/`: toàn bộ 3.062 JD, snapshot CSV nguồn/canonical, evidence, group và manifest; các trạng thái loại/cách ly vẫn được giữ.
- `catalogue/records.jsonl`, `catalogue/jobs.csv`: **788 JD ứng viên thực tế**, có văn bản và metadata. Đây là đầu vào catalog mở rộng, chưa phải dataset huấn luyện có nhãn.
- `catalogue/ids.json`, `groups.json`, `group_representatives.json`: ID, quan hệ nhóm và view đại diện tùy chọn.
- `catalogue/metadata_evidence.json`, `jd_audit.jsonl`: evidence và lý do sử dụng/giữ riêng từng record.
- `completed_benchmark_exposure.json`: overlay lịch sử đã dùng; không sửa run cũ.
- `cv_expansion_plan.json`: số JD/nhóm theo nghề, CV còn thiếu và khối lượng cặp dự kiến.

Hai run có **{len(hashes[0])}/{len(hashes[0])} file giống byte**. Ba CSV nguồn, 51 file pilot, run chuẩn bị và thí nghiệm Bước 4 không bị sửa. Không tạo nhãn, không train, không thay model đã đóng gói hoặc bảng điểm 50 JD, không nhập lịch sử vào database app hay đổi API/UI/VM. Artifact đầy đủ tiếp tục Git ignore; chỉ báo cáo/config/code được đưa vào cây nguồn.

## PowerShell

```powershell
Set-Location D:\\JobApply
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data verify --artifact .\\ml_data_runs\\20261116_jd_catalogue_v1_01
if ($LASTEXITCODE -ne 0) {{ throw 'Catalogue verification failed' }}

# Xem phân bố mà không mở toàn văn CSV lớn
Import-Csv .\\docs\\ml\\reports\\20261116-jd-role-coverage.csv | Format-Table

# Tái tạo vào thư mục mới
$jdOut = '.\\ml_data_runs\\jd_catalogue_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data expand-jd-catalogue --preparation .\\ml_data_runs\\20261114_pretraining_v3_01 --benchmark .\\ml_data_runs\\20261114_step4_v1_01 --output $jdOut
if ($LASTEXITCODE -ne 0) {{ throw 'Catalogue expansion failed' }}
```

**Bước tiếp theo:** xử lý phần metadata thiếu trên dữ liệu development, lên thiết kế CV mới theo phân bố nghề/nhóm thực tế, rồi khóa protocol và nhóm CV chưa sử dụng cho lượt đánh giá mới. Chỉ tăng catalog từ 50 lên 788 chưa chứng minh chất lượng ML đã tăng.
"""
    (out / "jd_catalogue_expansion.md").write_text(text, encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(build(args.first, args.second, args.output))
