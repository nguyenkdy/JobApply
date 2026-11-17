# Bộ thử trích xuất có cấu trúc — 17/11/2026

**Hướng hiện tại đã thay đổi theo yêu cầu người dùng:** không dùng LLM/API trả phí; tiếp tục bằng Python, regex và metadata có bằng chứng. Phần lựa chọn dịch vụ AI bên dưới chỉ là đề xuất lịch sử, chưa được thực hiện. Schema, fixture và kiểm tra evidence vẫn có thể tái sử dụng; không cần cấu hình tài khoản/API để tiếp tục hướng local. Xem [đối chiếu nhiệm vụ v4](task_matching_v4.md).

**Đã chuẩn bị và chạy baseline tại máy. Chưa chạy LLM; chưa có kết quả so sánh AI.** Chưa đổi nhãn, train, tạo CV hay thay API/UI/Docker/VM.

[Receipt từ run](reports/20261117-extraction-trial.json), [schema](schemas/structured_extraction_v1.schema.json), [định nghĩa nhãn đề xuất](recommendation_label_contract.md).

## Đã thực hiện

- Chọn cố định **41 hồ sơ development: 12 CV synthetic và 29 JD nguồn**, từ probe thời lượng và các hàng đợi thiếu task function/nghề. Hợp nhất ID trùng; không chọn theo nhãn/ranking. Tất cả vẫn development.
- Viết **24 tình huống đối chứng nhỏ** cho bắt buộc/ưu tiên, AND/OR, scope/thời lượng và nhiệm vụ. Đây là fixture do trợ lý soạn, không phải gold hoặc đánh giá độc lập; không chứa nhãn CV–JD.
- Baseline đạt **21/24 assertion**. Đây không phải accuracy trên 788 JD, không chứng minh model tốt hay xấu. Những tình huống chưa đạt:

- `FIXTURE_unknown_tool`
- `FIXTURE_task_paraphrase`
- `FIXTURE_task_analysis`

Ba trường hợp tương ứng: tên công nghệ ngoài từ điển, cách diễn đạt HTTP endpoints và nhiệm vụ phân tích dữ liệu. Giữ nguyên baseline để có kết quả đối chiếu, không sửa regex theo điểm fixture trong lượt này.

## Schema và kiểm tra bằng chứng

`ml_extraction_trial/contract.py` quy định claim kỹ năng, nhiệm vụ, thời lượng, cây logic; bắt buộc/ưu tiên/điều kiện và khẳng định/phủ định/unknown được giữ riêng. Evidence gồm field, trích nguyên văn và số lần xuất hiện; code tính offset Unicode, không bắt model đoán chỉ số ký tự.

Không có số tháng thì giữ null; không thay bằng 0. Có số tháng nhưng chưa rõ scope vẫn giữ số đã nêu cùng scope null. Thời lượng CV đã khai được biểu diễn `exact`, không tự đổi thành yêu cầu tối thiểu. Không đổi thực tập/dự án thành employment hoặc gán tổng năm cho mọi công nghệ.

Validator từ chối quote không có trong nguồn, sai ID/hash, trường ngoài schema, thiếu evidence, logic sai dạng và khoảng thời gian không hợp lệ. **Quote thật không chứng minh claim đúng ngữ nghĩa.** `claimed_complete` chỉ là tự khai; `coverage_verified=false`, `eligible_for_labeling=false` kể cả khi qua kiểm tra.

`requests.jsonl` chỉ chứa ID/kind/field/hash. Các assertion kỳ vọng, nhãn cũ, lý do chọn, ranking không được đưa vào request. `prompt.txt` yêu cầu coi văn bản là dữ liệu, không thực hiện hướng dẫn nằm trong CV/JD. Schema là hợp đồng nội bộ; cần kiểm adapter với dịch vụ đã chọn, chưa tuyên bố dùng trực tiếp được với mọi API.

## Giới hạn của baseline

Với hồ sơ trong kho, baseline lấy facts v3 đã khóa: có metadata upstream và chú thích viết kèm CV. **Không phải baseline chỉ đọc văn bản từ đầu.** Với fixture JD mới, chạy trực tiếp các hàm đọc JD v2/v3. Nếu LLM chỉ được nhận văn bản, hai phương pháp không có đầu vào tương đương trên kho thật; phải ghi rõ khi so sánh, không công bố thắng/thua chung từ số claim nhiều hơn.

## Phần LLM chưa thực hiện và lựa chọn dễ hiểu

Chưa phát hiện runtime Ollama/llama hoặc cấu hình API LLM qua các tên môi trường thông dụng; cache được kiểm chỉ có model embedding E5-small. Chưa có dịch vụ AI nào được gọi, chưa gửi CV/JD ra ngoài, chưa phát sinh phí suy luận trong lượt này.

Có hai hướng:

1. **Dùng AI qua Internet:** chương trình gửi văn bản tới dịch vụ và nhận JSON. Dễ bắt đầu thử lô nhỏ, cần tài khoản API có quyền sử dụng và thanh toán; dịch vụ nhận nội dung gửi đi. Chưa cấu hình client/provider hoặc mua dịch vụ.
2. **Chạy AI tại máy:** cần chọn/tải model và kiểm RAM/GPU. Việc đọc thông tin phần cứng bằng CIM bị từ chối trong phiên hiện tại, nên chưa kết luận máy đủ mạnh hoặc nên chọn model nào. Chưa tải/cài model.

Một ứng viên để thử qua Internet là GPT-6 Luna: trang chính thức hiện công bố hỗ trợ structured outputs, giá Standard $0,10/triệu token vào và $0,50/triệu token ra. Ví dụ minh họa 100.000 token vào + 100.000 token ra tương ứng $0,06; **đây không phải dự toán hoặc báo giá cho lô này**, chưa tính các yếu tố như retry, reasoning, thay đổi chế độ/giá. Nguồn kiểm ngày 17/11/2026: [OpenAI — GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Chưa chọn model cuối cùng và chưa có kết quả cho tiếng Việt trên dataset này.

## Nhập kết quả AI khi có cấu hình thực

Lệnh `ingest` chỉ kiểm kết quả đã có; **không gọi API**. Metadata cần provider/model/revision/settings và đúng hash prompt/schema. ID phiên bản do bên cung cấp khai được lưu, chưa xác thực độc lập; nếu chỉ có alias cập nhật theo thời gian thì không được tuyên bố đã khóa weights. Thiếu/trùng hồ sơ hoặc sai phiên bản bị từ chối; raw response giữ nguyên trong run mới. Fixture trong unit test có provider `test_fixture_only`, không phải lần chạy LLM thật.

```powershell
Set-Location D:\JobApply
$pythonML = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
& $pythonML -m ml_extraction_trial check --artifact '.\ml_data_runs\20261117_extraction_trial_v1_02'
if ($LASTEXITCODE -ne 0) { throw 'Extraction trial check failed' }

$trialOut = '.\ml_data_runs\extraction_trial_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& $pythonML -m ml_extraction_trial prepare --inventory .\ml_data_runs\20261117_document_inventory_v1_01 --output $trialOut
if ($LASTEXITCODE -ne 0) { throw 'Extraction trial failed' }
```

Khi có file phản hồi và metadata thật, lệnh là `python -m ml_extraction_trial ingest --trial <run> --responses <responses.jsonl> --metadata <metadata.json> --output <thư_mục_mới>`. Chưa tạo placeholder giả là kết quả model.

## Kiểm chứng

**188 test đạt**, 59.141 giây. Hai run `ml_data_runs/20261117_extraction_trial_v1_02` và `ml_data_runs/20261117_extraction_trial_v1_03` có **40/40 file giống byte**. Checker dựng lại danh sách mẫu, baseline, assertion, requests không lộ đáp án, hash/schema/prompt và chain dữ liệu. Run `_01` là snapshot trung gian trước bổ sung checker/runtime; không dùng làm bản hiện hành. Nguồn/pilot và nhãn v3 giữ nguyên.

Code mới: `ml_extraction_trial/`, `tests/ml/test_extraction_trial.py`, `scripts/report-extraction-trial.py`. Chưa thay module parser/luật v3. Kết quả hiện có chỉ là chuẩn bị và baseline; phép so sánh LLM còn cần cấu hình dịch vụ hoặc model local trước khi chạy.
