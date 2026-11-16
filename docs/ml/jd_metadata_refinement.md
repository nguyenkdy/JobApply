# Metadata catalog mở rộng và thiết kế CV — 16/11/2026

**Cập nhật sau báo cáo:** lô 200 CV v5 triển khai từ thiết kế bên dưới đã bị loại và xóa vì chỉ có một khung sinh thực tế. Các số CV/split dưới đây là kế hoạch lịch sử, không phải dữ liệu đang có. Kho JD/metadata và kết quả kiểm chứng trong báo cáo này được giữ nguyên. [Biên bản xóa](retired_expanded_cv_cleanup.md).

Đã chạy bộ bổ sung metadata `catalogue-metadata-v4-title-taxonomy` trên **788 JD / 698 nhóm**. Giữ đủ catalog, không sửa nguồn, ID, văn bản, nhóm, quality gate hoặc run cũ. Không tự nối lại bản cách ly để tăng số lượng.

[Receipt và kế hoạch máy đọc](reports/20261116-jd-metadata-v4.json), [phân bố nghề mới](reports/20261116-jd-metadata-role-coverage.csv), [nguồn catalog trước bổ sung](jd_catalogue_expansion.md).

## Đã thực hiện

| Metadata còn thiếu | Trước | Sau |
|---|---:|---:|
| Nghề | 308 | 136 |
| Kỹ năng | 95 | 65 |
| Stack | 172 | 110 |
| Thời lượng theo scope | 286 | 286 |

459 JD có thay đổi metadata; 278 thay đổi nghề, 278 thay đổi kỹ năng, 249 thay đổi stack. Các số này chồng nhau. Có cả sửa phân loại cũ (Fullstack từng bị xếp Frontend/Backend, quản lý từng bị gộp Business Analyst), không chỉ lấp ô trống.

Nghề được lưu ở ba mức: 631 theo quy tắc nghề, 21 chỉ biết Backend chưa rõ stack, 136 unknown hoặc xung đột. Nhãn generic không chứng minh cùng nghề cụ thể; khác chuỗi tên nghề không đủ kết luận không phù hợp.

Có **28 JD được quy tắc đánh dấu ngoài phạm vi benchmark phần mềm** (CNC/CAM, tự động hóa công nghiệp, giáo dục, kinh doanh, marketing, vật liệu). Chúng vẫn ở catalog 788; cần báo riêng nếu thiết kế benchmark giới hạn nghề. Không âm thầm đổi mẫu số thành một catalog nhỏ hơn.

Bổ sung từ vựng công nghệ cho mobile, dữ liệu, AI và các stack còn thiếu; lưu field, offset, nguyên văn evidence và phiên bản. Phân biệt thuật ngữ ưu tiên/không bắt buộc với core mention; ngay cả core mention cũng không chứng minh yêu cầu bắt buộc. Đã đối chiếu **12681 đoạn evidence**. Đây là độ phủ và tính khớp nguyên văn, **không phải điểm accuracy trên dữ liệu độc lập**.

Thời lượng kinh nghiệm không đổi: 286 JD còn thiếu. Trong số đó, 193 không có dạng thời lượng số được nhận diện trong requirements, 93 có số nhưng chưa xác định được scope/cận yêu cầu bằng quy tắc hiện tại. Không lấy số năm từ chức danh senior hoặc gán số tháng cho từng công nghệ.

Đã thêm chốt chặn ở `label_rules.py`: dữ liệu có `label_policy_status=requires_expanded_taxonomy_policy` trả `insufficient_evidence`, ô nhãn rỗng. Bộ luật cũ chưa được phép gán 0 cho Backend Java so với Fullstack chỉ vì khác tên. Chưa tạo nhãn CV–JD mới.

## Lịch sử dùng dữ liệu và artifact

Run hiện hành: `ml_data_runs/20261116_jd_metadata_v4_03`. `records.jsonl` và `canonical_jd_enriched.csv` chứa 788 JD với metadata mới; `jd_extraction_evidence.json` chứa bằng chứng; `metadata_changes.jsonl` ghi trước/sau và lý do còn thiếu. Snapshot trước sửa và các file nhóm/ID được giữ trong run.

Catalog đã được dùng phát triển bộ trích xuất. `metadata_use_exposure=development` và `exposure_overlay.json` đánh dấu toàn bộ các nhóm liên quan, kể cả record cùng nhóm nằm ngoài catalog. Cờ exposure lịch sử được giữ nguyên để truy vết. **Không dùng catalog này làm holdout JD mới**; vẫn có thể dùng làm kho JD đã biết trong protocol known-JD với CV mới chưa dùng chỉnh phương pháp.

Artifact mang loại `jd-metadata-refinement`, chưa phải dataset huấn luyện/split hoàn tất. Công cụ phải áp dụng overlay và chính sách taxonomy khi nhập tiếp; không bỏ các trường này để chạy luật cũ. 60 CV đã dùng ở Bước 4 tiếp tục là hồi quy.

## Thiết kế lô CV tiếp theo — chưa tạo CV

Đề xuất **200 CV synthetic mới**, 20 mỗi nghề dưới đây; bổ sung Fullstack theo phân bố thực tế. Đây là lô đầu để mở rộng độ phủ, chưa phủ mọi nghề trong kho; các nghề còn lại được liệt kê trong `cv_design_plan.json`, không bị loại khỏi mục tiêu.

| Nghề | JD hiện có | Nhóm JD | CV dự kiến |
|---|---:|---:|---:|
| backend python | 11 | 10 | 20 |
| backend java | 88 | 75 | 20 |
| frontend | 56 | 52 | 20 |
| devops/cloud | 14 | 14 | 20 |
| qa/testing | 39 | 39 | 20 |
| backend .net | 31 | 25 | 20 |
| fullstack | 90 | 80 | 20 |
| mobile | 50 | 47 | 20 |
| data engineer | 16 | 15 | 20 |
| ai/ml engineer | 37 | 26 | 20 |

Data Analyst vẫn thuộc mục tiêu nghiên cứu; nguồn trước đó không có JD ngoài development qua gate cho nhóm này. Cần phục hồi/bổ sung JD hợp lệ trước khi tuyên bố có benchmark positive cho Data Analyst. Các JD generic/unknown không được tự coi là Data Analyst.

Dự kiến 10 họ khung viết thực sự, mỗi họ hai CV cho mỗi nghề; từng kịch bản nguồn phải mới, độc lập với JD đích và ranking. Chia theo họ có thể cho **120/40/40 CV** (train/validation/test) nếu kiểm tra lineage/gần trùng không nối các họ lại. Đây là dự kiến, chưa phải split đã đạt. Không sửa mã họ để ép tỷ lệ.

Phủ employment, contract, internship, project và unknown. Không đổi thời gian dự án/thực tập thành thời gian làm nghề. Mọi skill/thời lượng phải có câu bằng chứng trong CV; không có danh tính thật; `is_synthetic=true`.

Schema CSV: `cv_id, cv_text, source_group, template_group, is_synthetic, role, skills, stack, experience_json, exposure, text_scope, lineage_json`. Skills/stack phân cách `;`; experience JSON là scope → tháng, unknown là `{}`. Lineage giữ scenario ID, generation version/cohort, họ khung thực, parent/ancestor và variant history. Sidecar evidence giữ câu trích, offset, scope và loại trải nghiệm. [Config CV hiện có](data_configs/new_cvs.template.json).

Với toàn catalog, validation/test lần lượt dự kiến **31,520 / 31,520 cặp**. Train lấy 10 random và tối đa 3 hard candidates mỗi loại role/stack/experience cho mỗi CV, tối đa 2,280 trước bỏ trùng/kiểm tra khả dụng. Hard candidate chưa phải nhãn 0. Chưa sinh các cặp hoặc nhãn này.

## Kiểm chứng và PowerShell

Hai lần chạy có **34/34 file giống byte**. Ba CSV nguồn và 51 file pilot giữ nguyên hash; manifest catalog đầu vào không đổi. Kết quả Bước 4 trên 50 JD không thay đổi. [Kiểm thử mã nguồn](../../TESTING.md).

```powershell
Set-Location D:\JobApply
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data verify --artifact .\ml_data_runs\20261116_jd_metadata_v4_03
if ($LASTEXITCODE -ne 0) { throw 'Metadata verification failed' }

$metadataOut = '.\ml_data_runs\jd_metadata_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe -m ml_data refine-jd-catalogue --catalogue-run .\ml_data_runs\20261116_jd_catalogue_v1_01 --output $metadataOut
if ($LASTEXITCODE -ne 0) { throw 'Metadata refinement failed' }
```

**Còn phải làm:** tác giả hóa CV mới theo thiết kế, kiểm lineage và tạo preview split; xây chính sách so nghề tương thích với Fullstack/generic/các nghề mở rộng trước khi gán nhãn. Chưa train lại, chưa tích hợp app hay thay đổi API/UI/Docker/VM. Dữ liệu synthetic và nhãn nội bộ chưa chứng minh chất lượng trên ứng viên thật.
