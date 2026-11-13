# JobApply — ML đề xuất việc làm từ CV

JobApply hướng tới chức năng: **ứng viên tải CV lên, hệ thống đọc năng lực chuyên môn và đề xuất Top 5 JD phù hợp đang mở trên website**. Trọng tâm là chuẩn hóa vị trí, kỹ năng, kinh nghiệm; so sánh keyword/BM25, embedding và học có giám sát để xếp hạng CV–JD.

Ví dụ cần kiểm chứng: CV Backend Python/Django 2 năm nên được ưu tiên cho JD Backend phù hợp hơn JD Data Analyst chỉ cùng chứa “Python”. Một từ khóa chung hoặc cosine cao chưa đủ chứng minh đáp ứng yêu cầu công việc.

**Trạng thái:** đã có ứng dụng tuyển dụng và pipeline ML offline trên **50 JD × 6 CV giả lập**. Đã train Logistic Regression, nhưng **chưa chốt model, chưa có test độc lập với nhãn được xác minh, chưa tích hợp matching vào upload CV**. Demo chỉ dùng CV giả lập/đã ẩn danh. Chức năng này đề xuất việc làm cho ứng viên, không tự quyết định tuyển dụng hay từ chối ứng viên.

README là tài liệu bàn giao cho người phát triển/Codex, đối chiếu với code và dữ liệu tại commit [2008a38d](https://github.com/nguyenkdy/JobApply/commit/2008a38d4d01455d3519048f6b48534156a556d1), ngày 12/11/2026. Các phần ghi **đề xuất/cần làm** chưa được triển khai chỉ vì xuất hiện trong tài liệu.

**Cập nhật Mốc 0 & Demo:** đã chạy lại baseline offline với môi trường/encoder khóa phiên bản, bảo toàn dữ liệu gốc và kiểm chứng hai run lặp; demo `recommend.py` chọn run qua `--run-dir` và xác minh toàn vẹn artifact trước khi suy luận. Xem [báo cáo và lệnh tái tạo Mốc 0](docs/ml/baseline.md).

**Cập nhật Mốc 2 v2 (13/11/2026):** đã sửa điều kiện trạng thái (`sections_found`, `needs_review=false`, cờ rỗng), thống nhất ngưỡng 80 ký tự chuẩn hóa và chạy upstream hai lần: cả 51 file output giống byte. Kho matching có **888 JD qua gate kỹ thuật, 65 bản trùng bị loại và 2.109 JD cách ly**; trong keep có **100 development và 788 prospective**. Lô 64 JD gồm **60 keep + 4 Data Analyst quarantine để rà parser**, không phải 64 JD sẵn sàng huấn luyện. Data Analyst có 9 tag nguồn, 8 dấu hiệu chức danh, 4 thuộc pilot và **0 ngoài pilot qua gate**. Chưa tạo CV mới hoặc khóa split; bước sau chỉ dùng số v2 đã xác nhận. [Hướng dẫn](docs/ml/dataset_pipeline.md), [receipt từ hai run](docs/ml/reports/20261113-data-preparation.json).

## 1. Đọc repo trước khi tiếp tục code

Đọc toàn bộ file được Git theo dõi, đặc biệt các nhóm dưới. Đối chiếu code/CSV thực tế thay vì chỉ dựa vào tài liệu tiến độ cũ.

- [jobapply_pilot_v1/](jobapply_pilot_v1/): dữ liệu và toàn bộ pipeline offline. Đọc `prepare_pilot.py`, `run_bm25.py`, `compare_embeddings.py`, `evaluate_top5.py`, `evaluate_topk.py`, `train_matcher.py`, `audit_pilot.py`, schema CSV và các kết quả.
- [jobapply_pilot_v1/jobapply_experience_v2/](jobapply_pilot_v1/jobapply_experience_v2/): `run_experiment.py`, `recommend.py`, CSV chú thích kinh nghiệm và `HUONG_DAN.md`. Entrypoint `train_matcher.py` ở thư mục con chuyển tiếp về trainer dùng chung ở thư mục pilot.
- [services/account/](services/account/): upload/download PDF, ownership, models và migrations. [services/job/](services/job/): danh mục JD, trạng thái và hạn ứng tuyển. [services/application/](services/application/): nộp hồ sơ, snapshot và lịch sử.
- [shared/runtime.py](shared/runtime.py): JWT, phân quyền, DB và gọi liên service. [frontend/src/](frontend/src/): luồng upload, API client, giao diện và kiểm thử client.
- [compose.yaml](compose.yaml), [scripts/](scripts/), [infra/](infra/), các Dockerfile, dependencies, migrations, [Nginx](frontend/nginx.conf), [Vite config](frontend/vite.config.js): vận hành và điểm nối service mới.
- [tests/](tests/), [frontend/e2e/](frontend/e2e/), [TESTING.md](TESTING.md): hợp đồng hành vi cần giữ và phạm vi kiểm thử trước đây.

Hướng dẫn app chi tiết được giữ ở [docs/application.md](docs/application.md); triển khai tại [docs/deploy-vm.md](docs/deploy-vm.md). [README_pilot.md](jobapply_pilot_v1/README_pilot.md) mô tả giai đoạn BM25 ban đầu nên câu “chưa chạy embedding/classifier” đã lỗi thời. [Báo cáo 10/11](jobapply_pilot_v1/JobApply_TienDo_2026-11-10.md) là lịch sử tiến độ. `results/run_report.json` chỉ ghi lần chạy BM25, không mô tả trạng thái toàn dự án.

## 2. Dữ liệu hiện có và nguồn gốc

### 2.1. Nguồn JD

Theo báo cáo tiến độ trong repo, nguồn thực tế là **Vietnamese IT Job Posting Data** từ [SonPhatTranDeveloper/IT-Job-Posting](https://github.com/SonPhatTranDeveloper/IT-Job-Posting), file `job_descriptions.csv` có 3.101 JD: LinkedIn 1.039, ITViec 929, TopCV 1.133. Kaggle Vietnam Jobs là nguồn tham khảo ban đầu, không phải nguồn của pilot hiện tại. Repo không có bằng chứng dùng dữ liệu Indeed.

Các liên kết quan sát được giữa các giai đoạn đã được kiểm tra từ ba CSV tại thư mục gốc; chưa khôi phục lịch sử biến đổi (chi tiết tại [docs/ml/dataset_pipeline.md](docs/ml/dataset_pipeline.md)):

1. `job_descriptions.csv` (`11.090.108` bytes, SHA256 `52801f88...`): `3.101` bản ghi nguồn (TopCV `1.133`, LinkedIn `1.039`, ITViec `929`), chưa có `job_id`, có `2.669` dòng chứa byte không hợp lệ UTF-8 và `3.075` dòng chứa ký tự thay thế `U+FFFD`.
2. `jobs_clean.csv` (`14.384.924` bytes, UTF-8 BOM, SHA256 `a9308c6e...`): `3.062` JD có `job_id` duy nhất, không thấy byte UTF-8 lỗi hoặc `U+FFFD` trong bản hiện có; liên kết về `3.062` dòng chính (`source_row_number`) và `38` dòng phụ gộp trong `source_records_json` (`3.100/3.101` dòng raw khớp `(site, job_url)`); dòng raw duy nhất không liên kết là dòng `1141` (`description` dài 12 ký tự).
3. `jobs_matching.csv` (`11.197.747` bytes, UTF-8 BOM, SHA256 `2f771640...`, `pipeline_version=1.0.0`): giữ nguyên `3.062` `job_id`, khớp `source_description_sha256` trên `3.061/3.062` dòng (trừ `job_906e26bf2136f879aba5`); tách nhiệm vụ, yêu cầu, ưu tiên và ghép `match_text`. Có `713` dòng `tasks_text` và `134` dòng `requirements_text` bị lỗi công thức bảng tính `#NAME?` được cổng chất lượng Mốc 2 cách ly.
4. `jobs_pilot.csv`: `50` JD được chọn có chủ đích (`50/50` khớp `source_match_text_sha256` với `jobs_matching.csv`, `11` bản chỉnh sửa có nhật ký trong `pilot_edits.csv`).

**Ba CSV nguồn lớn được giữ nguyên byte tại máy local và Git ignore.** Chưa tìm thấy script lịch sử sinh clean/matching trong phạm vi workspace đã kiểm kê; `prepare_pilot.py` chỉ tiêu thụ hai file đó. Mốc 2 dùng `python -m ml_data upstream` (`adapter_version=upstream-observation-v2`) để kiểm định, lưu snapshot nguyên bản và nhập matching một lần; `historical_pipeline_reproduced=false`.

Tin từ nền tảng uy tín không tự trở thành nhãn CV–JD. Các trường công nghệ do LLM trích xuất ở nguồn chưa được dùng làm nhãn chuẩn. Dữ liệu JD lịch sử có thể hết hạn và **không tự nhập thành tin đang tuyển trong database app**.

### 2.2. Pilot trong repo

- `jobs_pilot.csv`: 50 JD, gồm Python Backend 10, Java Backend 10, Frontend 10, DevOps/Cloud 8, QA/Testing 8, Data Analyst 4. Nguồn: ITViec 22, LinkedIn 16, TopCV 12. Data Analyst chỉ có tin ITViec; mẫu chưa đại diện thị trường.
- `selection_manifest.csv`: ID/lý do chọn. `pilot_edits.csv`: 21 chỉnh sửa. `content_group_id` hỗ trợ tránh trùng mô tả chính xác, chưa thay thế kiểm tra gần trùng.
- `cvs_synthetic.csv` và `synthetic_cv_texts/`: 6 CV giả lập. Lần lượt là Python/Django 24 tháng, Data Analyst 24 tháng, Java 36 tháng, Frontend React 12 tháng, DevOps 24 tháng, QA Automation 24 tháng.
- `judgments_ai_draft.csv`: 300 cặp, gồm 211 nhãn 0, 71 nhãn 1, 18 nhãn 2, kèm `rationale` giải thích cơ sở chấm điểm cho từng cặp.
- `results/judgments_template.csv`: 300 cặp mẫu khung dữ liệu. `results/hard_pair_candidates.csv`: 21 cặp khó đề xuất.

Một hàng nhãn thuộc **cặp (cv_id, job_id)**. Cùng JD có thể phù hợp CV này nhưng không phù hợp CV khác. 300 cặp chỉ xuất phát từ 6 CV, không phải 300 ứng viên độc lập.

### 2.3. Vấn đề kỹ thuật đã xử lý ở Mốc 0

1. Header hiện tại của `judgments_ai_draft.csv` là `cv_id,job_id,relevance_0_1_2,,rationale`: cột thứ tư mất tên và cả 300 giá trị đều trống. Mốc 0 chuẩn hóa sang file dẫn xuất có đầy đủ tên cột và hash phiên bản văn bản mà không sửa file gốc.
2. `results/embedding_vs_bm25.csv` hiện có điểm đọc được. Bản `embedding_vs_bm25_backup_20261110_163750.csv` có 277 giá trị BM25 không parse được, ví dụ `64.431.045`. Loại backup khỏi input manifest; không sửa số bằng xóa dấu chấm. Nếu thiếu bản đúng, tạo lại điểm từ văn bản.
3. Trong snapshot Git chuẩn hóa LF, bốn checksum trong `results/experience_v2/run_info.json` không khớp byte. Ba checksum điểm/chú thích kinh nghiệm khớp khi chuyển sang UTF-8 BOM + CRLF; checksum nhãn chưa khớp với các biến thể BOM/LF/CRLF đã kiểm tra. Giá trị nhãn và hai feature vẫn khớp các bảng training/prediction đã lưu, nhưng chưa khôi phục đầy đủ lịch sử artifact.
4. Tại thời điểm bàn giao ban đầu chưa có lockfile ML/revision E5. Mốc 0 hiện có `requirements-ml-win-py314.lock.txt` và `encoder.lock.json`, được xác minh trên môi trường Windows CPython 3.14.3 hiện có; dependency backend vẫn tách riêng.

Mốc 0 dùng `run_baseline.py` để giữ bản gốc, tạo bản nhãn dẫn xuất có nhật ký, snapshot/manifest và tái chạy vào thư mục mới. Trên working copy Windows ngày 12/11, ba checksum điểm/chú thích khớp byte; Git blob chuẩn hóa LF vẫn khác checksum cũ. Chi tiết và lệnh tái tạo: [Mốc 0](docs/ml/baseline.md).

## 3. Các phương pháp đã chạy

### 3.1. Keyword/BM25

`run_bm25.py` có keyword overlap và BM25 positive-IDF, `k1=1.5`, `b=0.75`; mỗi từ query khác nhau được tính một lần. Tokenizer chuẩn hóa Unicode, một số alias kỹ thuật và giữ Java/JavaScript, C++/C# riêng biệt. Tách từ tiếng Việt còn đơn giản.

Đầu vào là `cv_text` và `match_text`. Nhóm chọn mẫu, công ty, nguồn, URL, ID và thông tin cá nhân không phải feature. BM25 không được train bằng nhãn 0–1–2. Kết quả ở `results/rankings_all.csv`, `results/top_matches.csv`; `rank_keyword` là baseline đếm token chung.

### 3.2. Embedding

`compare_embeddings.py` dùng **intfloat/multilingual-e5-small trên CPU**, chưa fine-tune. CV thêm `query: `, JD thêm `passage: `; vector chuẩn hóa và so bằng cosine.

Văn bản vượt giới hạn token của model được chia đoạn, kể cả một dòng quá dài. Vector đoạn được trung bình có trọng số số token rồi chuẩn hóa lại. Cách này giảm mất nội dung do cắt ở 512 token, chưa đảm bảo hiểu đúng mọi yêu cầu; pooling vẫn cần đánh giá trên validation.

`results/embedding_vs_bm25.csv` chứa 300 cặp, điểm và thứ hạng hai phương pháp. `rank_gain = rank_bm25 - rank_embedding` chỉ biểu diễn đổi vị trí, không chứng minh tốt hơn khi chưa đối chiếu nhãn. Cosine 0,90 không có nghĩa phù hợp 90%.

### 3.3. Classifier cơ bản

`train_matcher.py` ghép theo cả hai ID, huấn luyện **StandardScaler + Logistic Regression** với `C=1.0`, `solver=lbfgs`, `max_iter=2000`.

- X: `bm25_score`, `cosine`.
- y: `relevance_0_1_2`.
- Điểm xếp hạng: `P(y=1) + 2 × P(y=2)`, thang 0–2.
- Không đọc trực tiếp CV/JD hoặc rationale. Recall/NDCG là metric đánh giá, không phải feature.

Đây là **phân loại từng cặp rồi xếp hạng bằng kỳ vọng nhãn**, chưa phải learning-to-rank tối ưu trực tiếp theo nhóm query. E5 là model pretrained tạo biểu diễn; Logistic Regression là model đã train trên nhãn pilot. BM25/cosine vừa là baseline, vừa là feature của classifier.

Đánh giá leave-one-CV-out: train 5 CV/250 cặp, giữ riêng 1 CV/50 cặp, lặp 6 lượt. Scaler chỉ fit trên train. Tuy nhiên 50 JD dùng chung giữa các lượt và pilot đã được xem khi phát triển, nên đây không phải final test độc lập cho CV/JD mới.

Sau đánh giá, script fit lại 300 cặp và lưu `results/supervised/match_classifier.joblib`. Suy luận bằng model này trên CV cũ chỉ minh họa đầu ra; không thay cho dự đoán held-out.

### 3.4. Classifier bổ sung kinh nghiệm

`jobapply_experience_v2/run_experiment.py` thêm `coverage` và `gap_years_input`. `cv_experience.csv`, `jd_experience.csv` là **chú thích riêng cho pilot**, có câu bằng chứng; chưa phải bộ trích xuất kinh nghiệm tự động cho tài liệu mới.

- Chỉ so thời lượng trong cùng phạm vi nghề/kỹ năng có bằng chứng. Liệt kê AWS trong skills không đủ gán toàn bộ số năm làm việc thành kinh nghiệm AWS.
- `coverage`: tỷ lệ điều kiện kinh nghiệm có thể đối chiếu, không phải tỷ lệ khớp tất cả skill.
- `gap_months_observed`: mức thiếu lớn nhất trong các điều kiện so được. CV DevOps 24 tháng, JD cần 60 tháng DevOps → thiếu 36 tháng.
- Thiếu bằng chứng giữ `unknown`; đầu vào số dùng gap 0 kèm coverage để biểu diễn mức quan sát. Gap 0 không chứng minh đáp ứng toàn JD khi còn điều kiện chưa đo được.
- Quy ước “trên 3 năm” thành ít nhất 37 tháng là giả định của pilot cần ghi vào rubric và rà lại khi tổng quát hóa.

Chỉ 45/300 cặp có gap đo được; 28 cặp có gap dương. Có đối chứng `coverage_control` để tách tác động của mức thiếu khỏi tác động của việc có thông tin đối chiếu. `recommend.py` vẫn chạy trên 50 JD pilot, không truy vấn database app.

## 4. Kết quả hiện tại — thống nhất Top 5

Các bảng trong repo ghi:

- **BM25:** Recall@5 **0,3016**; NDCG@5 **0,4493**.
- **Embedding E5:** Recall@5 **0,5476**; NDCG@5 **0,6748**.
- **Classifier cơ bản:** Recall@5 **0,5476**; NDCG@5 **0,6678**.
- **Coverage control:** Recall@5 **0,5476**; NDCG@5 **0,6458**.
- **Experience classifier:** Recall@5 **0,6270**; NDCG@5 **0,7661**.

Nguồn lịch sử: [supervised/metrics_by_cv.csv](jobapply_pilot_v1/results/supervised/metrics_by_cv.csv), [experience_v2/macro_metrics.csv](jobapply_pilot_v1/results/experience_v2/macro_metrics.csv) và các `held_out_predictions.csv`. Mốc 0 đã encode/train lại và tái tạo các metric trên: [bảng run mới](docs/ml/reports/20261112-macro_metrics.csv). Điểm số có sai khác nhỏ với lịch sử, được ghi trong [báo cáo](docs/ml/baseline.md); thứ hạng và metric giữ nguyên.

**Recall@5** của một CV = số JD nhãn 2 trong Top 5 / tổng JD nhãn 2 của CV trong danh mục 50 JD đã chấm. Tìm được 2 trong 3 JD nhãn 2 → Recall = 2/3. Không phải tỷ lệ năm đề xuất đúng.

**NDCG@5** xét mức phù hợp và vị trí. Script tính `DCG@5 = Σ (2^label_i − 1) / log2(i+1)` với i từ 1 đến 5, rồi chia DCG của thứ tự lý tưởng trong cùng danh mục. Gain nhãn 2/1/0 lần lượt là 3/1/0. NDCG không phải Accuracy.

Macro là trung bình theo CV. CV không có nhãn 2 có Recall không xác định; mọi nhãn 0 thì NDCG không xác định. Báo cáo số CV được tính/bị loại, không tự gán các trường hợp đó thành 0 hoặc 1.

Theo nhãn hiện tại, embedding tốt hơn BM25; classifier hai feature chưa cải thiện. Bản kinh nghiệm có điểm pilot cao hơn nhưng **chưa đủ căn cứ chốt model**: mẫu nhỏ, nhãn AI, feature đã được thiết kế sau khi xem lỗi pilot và provenance còn cần xử lý. Các số đo mức đồng thuận với nhãn thử nghiệm, chưa chứng minh chất lượng tuyển dụng thực tế.

## 5. Ưu tiên 1 — Tiêu chí chấm điểm dựa trên bằng chứng

Việc chấm độ phù hợp CV–JD phải bám sát tiêu chí rõ ràng và trích dẫn bằng chứng cụ thể từ văn bản CV và JD:

### 5.1. Định nghĩa relevance

Câu hỏi đánh giá: **“Dựa trên năng lực được ghi trong CV, JD này có đáng được đề xuất để ứng viên xem và cân nhắc ứng tuyển không?”** Không gán xác suất được tuyển, không suy đoán năng lực chưa ghi.

Đánh giá nhiệm vụ/vai trò, kỹ năng cốt lõi, kinh nghiệm đúng phạm vi và điều kiện chuyên môn bắt buộc khác. Tách must-have và nice-to-have. Không suy nhãn từ title hoặc score BM25/cosine.

Các mức độ phù hợp:

- **2 — Phù hợp cao:** có bằng chứng rõ về vai trò/nhiệm vụ và skill cốt lõi, đáp ứng các yêu cầu bắt buộc đã xác định, không còn khoảng thiếu quan trọng chưa giải quyết. Thiếu một ưu tiên không tự động loại nhãn 2.
- **1 — Phù hợp một phần:** liên quan thực chất nhưng có khoảng thiếu cần cân nhắc hoặc bằng chứng chưa đầy đủ, vẫn đủ để đánh giá mức một phần theo tiêu chí.
- **0 — Không phù hợp:** lệch nhiệm vụ cốt lõi hoặc có bằng chứng không đáp ứng điều kiện bắt buộc quan trọng. Khác tên nghề không phải lý do duy nhất.
- **needs_review / insufficient_evidence:** không đủ thông tin để kết luận, JD mâu thuẫn hoặc yêu cầu chưa rõ. Đây là trạng thái xử lý dữ liệu, không phải nhãn thứ tư đưa ngay vào classifier. Để trống relevance đến khi giải quyết; không ép thành 0.

Không dùng “thiếu một tháng kinh nghiệm = 0” cho mọi JD. Cần xét mốc tối thiểu, khoảng năm, thực tập, bán thời gian, kinh nghiệm chồng thời gian và kỹ năng chuyển đổi. Thiếu thông tin không đồng nghĩa không có kinh nghiệm.

Ví dụ: CV Python/Django 24 tháng có REST API/PostgreSQL gặp JD Backend yêu cầu tương ứng là 2 nếu các yêu cầu bắt buộc khác được đáp ứng. JD Data Analyst cùng có Python nhưng cần BI/phân tích kinh doanh phải xét bằng chứng riêng; không tự động gán 0 chỉ vì khác nhóm nghề.

### 5.2. Schema cặp dữ liệu và bằng chứng

Khi chuẩn bị các cặp CV–JD trong pipeline dữ liệu (`ml_data sample`), mỗi cặp lưu phiên bản văn bản và bằng chứng rõ ràng:

- Schema cặp trong pipeline Mốc 2: `pair_id`, `partition`, `cv_id`, `jd_id`, `cv_version`, `jd_version`, `cv_text`, `jd_text`, `label_status`, `relevance_0_1_2`, `cv_evidence`, `jd_evidence`, `rationale`.
- Mỗi nhãn hoàn tất cần trích dẫn bằng chứng từ cả CV (`cv_evidence`) và JD (`jd_evidence`) cùng lý do (`rationale`), truy về đúng phiên bản văn bản (`cv_version`, `jd_version`) và không chứa PII.

## 6. Ưu tiên 2 — Thêm CV/JD đa dạng và hard negatives

Các số lượng sau là **mục tiêu đề xuất cho vòng mở rộng**, trong đó phần JD upstream đã được kiểm chứng và nhập vào kho chuẩn ở Mốc 2 ([docs/ml/dataset_pipeline.md](docs/ml/dataset_pipeline.md)).

### 6.1. Mở rộng dữ liệu

Đề xuất khoảng **60 CV train, 20 CV validation, 300 JD development**, ngoài bộ final test riêng ở mục 7.

- Bao phủ sáu nhóm nghề ban đầu với nhiều mức Intern/Junior/Middle/Senior, stack, nhiệm vụ, thời lượng và mức đầy đủ bằng chứng. Không chỉ đổi tên/diễn đạt lại một CV để tăng số lượng.
- Thêm nhóm dễ nhầm: Python Backend/Data Analyst/QA Automation; Java/JavaScript; DevOps/Backend biết Docker; manual QA/automation; React/React Native.
- Có CV ngắn/dài/đa cột, tiếng Việt và Việt–Anh, chuyển nghề, có dự án nhưng ít kinh nghiệm. Ghi ngôn ngữ và dạng tài liệu để phân tích lỗi.
- Tạo CV giả từ hồ sơ nghề độc lập với JD mục tiêu; lưu `template_group` và lịch sử tạo. CV thật cần quyền sử dụng và ẩn danh; không đưa CV thật lên repo công khai.
- Phân tầng JD theo nghề, kinh nghiệm, nguồn và thời gian. Tránh một nghề chỉ xuất hiện ở một nền tảng; lưu raw, normalized, quality flags và quyết định giữ/loại.
- Deduplicate chính xác và rà gần trùng/cross-posting. Không loại mẫu khó chỉ vì model xếp sai. Không âm thầm dịch tài liệu rồi coi nhãn/đặc trưng vẫn không đổi.

### 6.2. Tạo negative pairs khó đúng cách

Sau chia tập, mining **chỉ trên train**: lấy hợp các JD điểm cao từ BM25/E5, thêm cặp cùng stack khác nhiệm vụ, đúng nghề nhưng khác yêu cầu quan trọng, và một phần cặp dễ/ngẫu nhiên.

Chỉ cặp có căn cứ xác định nhãn 0 mới là negative; nhãn 1 vẫn là phù hợp một phần. Không coi JD ngoài Top k, cặp chưa chấm hoặc khác nghề là negative mặc định. Giữ positives và nhiều mức khó; lưu `sampling_strategy`, `mining_model_version`.

Ngân sách khởi điểm: 40 cặp/CV train × 60 CV = 2.400 cặp, gồm hợp top candidates và mẫu ngẫu nhiên; điều chỉnh theo phân bố nhãn thực tế. Đây là sampling để train, không phải denominator Recall trên toàn bộ 300 JD.

## 7. Ưu tiên 3 — Test độc lập và chống rò rỉ

Pilot 6 CV/50 JD đã dùng để chọn cách làm nên giữ làm **development/regression**, không đổi tên thành final test. Chia theo CV gốc/họ template, không random các hàng để cùng CV ở cả train và test.

Protocol vòng tiếp theo đề xuất:

1. **Train:** 60 CV mới với kho JD hợp lệ; được mining và thử feature.
2. **Validation:** 20 CV mới, không chung họ template với train. Chọn trước 100 JD hợp lệ, đánh giá đầy đủ 20 × 100 = 2.000 cặp. Dùng để chọn model, hyperparameter, pooling và ngưỡng.
3. **Final test:** 20 CV mới và 100 JD giữ riêng, không trùng/gần trùng development, chấm đủ 2.000 cặp có đầy đủ bằng chứng. Đây là phép thử **cả CV mới và JD mới**, khó hơn leave-one-CV-out trên kho chung.

Nếu hạn chế nguồn lực, có thể bắt đầu final test 10 CV × 50 JD = 500 cặp. Báo cáo rõ giới hạn bộ nhỏ. Không tiết kiệm bằng cách gán 0 cho cặp chưa đọc.

Recall@5 chỉ nói về danh mục 50/100 JD đã chấm đầy đủ, không phải thị trường. Nếu dùng pooled judgments trên kho lớn, ghi phạm vi pool và độ phủ; không gọi pooled Recall là recall toàn kho. Có thể thêm test riêng cho “CV mới, kho JD quen thuộc”, nhưng báo cáo tách với test cả CV/JD mới.

**Khóa trước khi thử model:** split manifest, seed, group IDs, hash nội dung, rubric/label version, k=5, gain NDCG và cách xử lý metric không xác định. Kiểm tra CV/template không giao nhau; test JD không cùng nhóm gần trùng development. Không dùng `target_role`, `pilot_group`, nguồn, ID hoặc rationale như feature tắt để đoán nhãn.

Người quản lý test giữ nhãn ngoài thư mục mà Codex đọc để chỉnh model, chấm bằng evaluator riêng sau khi khóa cấu hình. Nếu Codex đọc toàn bộ repo công khai thì không thể coi test labels trong repo là giữ kín. Công khai dữ liệu train/validation khi được phép; quản lý quyền truy cập final-test labels riêng.

Sau test, báo cáo kết quả thực đo. Nếu dùng lỗi test để chỉnh model, bộ đó trở thành development cho vòng sau và cần test mới. Báo cáo từng CV/nhóm, chênh lệch, số mẫu và khoảng bất định bằng bootstrap theo CV khi đủ mẫu; không coi mọi cặp là quan sát độc lập.

## 8. Chuẩn hóa đầu vào dùng chung offline/online

**Cần triển khai** pipeline tổng quát thay cho chú thích thủ công 50 JD:

1. Trích PDF có text; nhận biết scan, rỗng, mã hóa, thứ tự đọc sai, quá dài. MVP có thể báo không trích được và yêu cầu PDF có text; OCR là mở rộng được đánh giá riêng.
2. Tách nội dung chuyên môn khỏi tên, tuổi/ngày sinh, giới tính, email, điện thoại, địa chỉ và thông tin nhận diện. Không nối nguyên raw PDF hoặc `candidate_snapshot` vào encoder.
3. Chuẩn hóa title thành họ nghề/seniority có bằng chứng; không ép mọi title thành một nhãn nghề duy nhất.
4. Skill dùng alias có version, giữ Java/JavaScript, React/React Native khác nhau; phân biệt “đã dùng”, “đang học”, “chưa có kinh nghiệm”. Có từ skill không đủ xác nhận năng lực.
5. Experience lưu scope, tháng/khoảng thời gian, evidence và known/unknown. Không suy từ tuổi/năm tốt nghiệp; không cộng chồng công việc song song thành gấp đôi thời gian.
6. JD tách tasks/must-have/nice-to-have, lưu câu gốc/offset, parser version, confidence/cờ review. Không đặt số năm cho yêu cầu mơ hồ.

JSON phù hợp cấu trúc lồng nhiều skill/điều kiện; CSV phù hợp bảng cặp/metric. JSON không phải điều kiện để ML hoạt động. Quan trọng là schema/version và phép chuyển đổi được kiểm tra.

Đánh giá extraction riêng trên tài liệu người đã duyệt: precision/recall skill, độ đúng role, scope/thời lượng kinh nghiệm, xử lý unknown và rò PII. Ranking tốt trên CSV chuẩn bị sẵn chưa chứng minh PDF parser tốt. So text-only với structured features trên cùng validation trước khi bật feature mới.

## 9. Thí nghiệm model và kiểm tra thông tin nhạy cảm

### 9.1. Huấn luyện tiếp theo

- Giữ keyword, BM25, E5 và classifier hai feature làm đối chứng. Bản kinh nghiệm có ablation coverage-only/gap để biết phần nào đóng góp.
- Với kho lớn, thử hợp Top N BM25/E5 rồi rerank. Chọn N trên validation và đo độ phủ retrieval; reranker không cứu được JD bị bỏ từ bước trước. Pilot hiện chấm toàn bộ 50 JD.
- Thử skill coverage, role/task similarity, experience gap khi extractor đủ tin cậy. Không boost thủ công chỉ để sửa một ví dụ đã xem.
- Khi đủ nhãn, thử learning-to-rank theo nhóm `cv_id`, ví dụ LambdaMART, cùng split/candidates/features với classifier. Chưa triển khai LTR trong snapshot hiện tại.
- Scaler/imputation/feature selection chỉ fit trên train. Chọn cấu hình trên validation, final test sau khi khóa. E5 vẫn frozen; fine-tune là lựa chọn sau, không bắt buộc cho MVP.
- Nếu supervised không thắng baseline ổn định, dùng baseline cho demo và báo cáo đúng; không ép ML có giám sát phải thắng.

Bundle model cần thứ tự feature, rubric/label/split/data versions, hashes, code commit, preprocessing version, encoder revision, dependency lock và metric. Cache embeddings theo hash nội dung + encoder + preprocessing. Không tải model hoặc encode lại toàn kho mỗi request.

### 9.2. Fairness/proxy audit

`audit_pilot.py` hiện **chỉ kiểm tra BM25**. Metadata bị loại khỏi scorer → 30/30 biến thể giữ điểm, chỉ xác nhận allowlist. Cố ý nối metadata vào text → 9/30 cặp đổi thứ tự Top 5, 2/30 đổi Top 1. Chưa kiểm chứng tương đương E5/classifier/PDF pipeline; không được ghi “đã loại bỏ bias”.

Tạo cặp CV giả giữ chuyên môn nguyên vẹn, chỉ đổi tên, giới tính, tuổi, địa chỉ; thêm proxy tên trường/tổ chức nhưng giữ bằng cấp, ngành và nhiệm vụ. Chạy qua **trích xuất → ẩn danh → retrieval → reranking**. Đo thay đổi text chuyên môn, score, Top 1, thành viên/thứ tự Top 5 và độ dịch chuyển hạng. Cặp biến thể ở cùng partition.

Nếu thiết kế loại một thuộc tính, text chuyên môn sau xử lý cần giống nhau; scorer xác định cần cùng kết quả trong tolerance đã quy định. Điều tra mọi khác biệt. Thử nhiều cách biểu đạt để không chỉ test đúng regex đã viết. Không đổi trên ít mẫu không chứng minh công bằng với mọi nhóm.

Địa điểm làm việc có thể là **bộ lọc người dùng chủ động chọn**, tách khỏi điểm năng lực. Không suy từ địa chỉ nhà; không dùng danh tiếng trường/công ty, năm tốt nghiệp, khoảng trống nghề nghiệp làm proxy mặc định. Không suy đoán thuộc tính nhạy cảm của CV thật để lập báo cáo nhóm.

## 10. Tích hợp ứng dụng — thiết kế đề xuất

### 10.1. Hợp đồng hiện có

App dùng React/Vite, ba FastAPI service, PostgreSQL với database riêng account/job/application. Nginx có `/api/account`, `/api/job`, `/api/application`. Browser gọi API tương đối; liên service dùng HTTP/JWT, không join DB của nhau.

- Account nhận PDF tối đa 5 MB, kiểm tra cấu trúc và lưu volume. `/cvs/{id}/snapshot` kiểm tra chủ sở hữu nhưng chỉ trả metadata/profile, **chưa có text chuyên môn**.
- Job public search chỉ trả Published và chưa hết hạn. API tối đa 100 tin/trang; UI lấy 12. Recommendation không được chỉ chấm trang đầu.
- Application giữ snapshot khi nộp, quyền download và chuyển trạng thái; thêm ML phải giữ các hành vi này.
- ID pilot `job_...`/`CV_SYN_...` khác UUID app; không trả ID pilot làm link JD app nếu chưa có mapping thật.

### 10.2. Luồng cần xây

1. Candidate đăng nhập, upload/chọn CV của mình. Upload vẫn thành công khi recommendation tạm lỗi; hiển thị trạng thái xử lý riêng.
2. Account xác minh ownership, trích/chuẩn hóa chuyên môn hoặc cung cấp API nội bộ có quyền cho module xử lý. Không nhận đường dẫn file tùy ý, không lộ storage path/CV người khác.
3. **Đề xuất thêm Recommendation Service** dùng package ML chung; nhận `cv_id`, kiểm tra Candidate/JWT và ownership qua Account; lấy catalog hợp lệ từ Job qua API có phân trang/version.
4. Retrieval/rerank, kiểm tra lại trạng thái và deadline trước trả kết quả; tin vừa đóng phải bị loại và lấy bù từ danh sách hợp lệ.
5. Trả Top 5 với UUID app, lý do có evidence và thông tin chưa xác định. Nếu ít hơn 5 kết quả hợp lệ/đủ điều kiện, trả ít hơn 5.
6. UI có chọn CV, nút “Gợi ý việc làm từ CV”, loading/error/empty, link xem JD/ứng tuyển. Không hiển thị score như “% được tuyển”.

API **đề xuất, chưa tồn tại**: `POST /api/recommendation/recommendations`, body `{"cv_id":"<app-cv-uuid>","top_k":5}`. Response cần `model_version`, `cv_version`, `catalog_version`, trạng thái và items `{job_id, rank, score, score_type, reasons, missing_evidence}`. Score ghi rõ loại/thang; không nhận owner_id/score do client áp đặt. Lý do dựa evidence, không dùng lời giải thích AI bịa như bằng chứng model.

Chưa có quality threshold đáng tin cậy: không tự đặt cosine 0,8 thành “phù hợp”. Chọn threshold/abstention trên validation; phân biệt không có JD, không trích được CV, thiếu bằng chứng và lỗi dịch vụ.

### 10.3. Điểm kỹ thuật cần xử lý

- Backend hiện nhắm Python 3.14; Mốc 0 đã kiểm tra và khóa môi trường ML Windows CPython 3.14.3 riêng. Môi trường ML Linux/container còn cần xác minh. Không mặc định joblib tương thích mọi phiên bản; chỉ nạp artifact tin cậy do dự án tạo.
- `shared.runtime.remote()` trả JSON, timeout 5 giây; không dùng nguyên hàm này để tải PDF binary hoặc cold inference dài. Warm model lúc startup, cache JD, giới hạn thời gian; chỉ thêm background task/polling nếu latency thực tế cần.
- Cache theo quyền sở hữu/phiên bản CV, không lộ dữ liệu chéo user. Không log raw CV/JWT/PII; giới hạn trang/token/thời gian xử lý.
- Version index/catalog theo lifecycle JD. BM25 phụ thuộc corpus: đổi kho tin làm đổi phân bố score; phải đánh giá classifier khi chuyển từ 50 JD sang kho mới.
- Seed hiện tạo PDF trang trắng và JD mô tả chung, **không đủ demo ML có ý nghĩa**. Tạo PDF giả có text và JD demo đa dạng qua API, lưu mapping/provenance; không nhập toàn bộ tin lịch sử thành đang tuyển.
- Giữ bất biến migrations `0001_initial.py`; thêm migration mới nếu cần. Bổ sung Nginx/Vite proxy, Compose, healthchecks và tests cho service mới.

## 11. Lộ trình và điều kiện hoàn tất

### Mốc 0 — Baseline có thể tái tạo

Đã triển khai runner `jobapply_pilot_v1/run_baseline.py`, validation/metric dùng chung, CLI với CV/JD/k động, lock môi trường Windows và E5 revision/hash. Runner tái tạo điểm từ văn bản, đánh giá leave-one-CV-out, lưu config/split/hash/source snapshot vào thư mục run mới, từ chối ghi đè. Báo cáo kiểm chứng và giới hạn tại [docs/ml/baseline.md](docs/ml/baseline.md). Đây là baseline kỹ thuật của pilot, chưa phải nghiệm thu chất lượng model.

### Mốc 1 — Demo chọn đúng run và xác minh artifact

Đã hoàn tất cập nhật `jobapply_pilot_v1/jobapply_experience_v2/recommend.py` và `jobapply_pilot_v1/run_artifacts.py`: bắt buộc `--run-dir`, xác minh manifest, checksum, cấu hình encoder/BM25, thứ tự feature và tương thích preprocessing trước khi suy luận; hỗ trợ CV mới dạng văn bản chuyên môn đã ẩn danh mà không trộn artifact ngoài run.

### Mốc 2 — Kiểm chứng upstream, nhập JD và chia tập chống rò rỉ

Đã kiểm kê ba CSV upstream, đối chiếu `raw → clean → matching → pilot`, nhập `3.062` JD (`888` keep, `65` trùng, `2.109` cách ly), cô lập `68` record liên quan pilot và chọn **64 JD development: 60 keep + 4 ca rà parser** ([hướng dẫn](docs/ml/dataset_pipeline.md), [danh sách](docs/ml/reports/20261113-upstream-jd-selection.json)). Kết quả v2 đã được xác minh hai run và 44 test. Cần giải quyết thiếu JD Data Analyst qua gate, bổ sung CV mới có lineage theo [schema/config](docs/ml/data_configs/new_cvs.template.json), rồi mới rà phân bố và khóa split. Giữ nhãn pilot/provenance; không tự tạo gold hoặc đổi `ai_draft` thành nhãn người.

### Mốc 3 — Extraction và benchmark

Xây parser dùng chung, đo extraction; chạy các baseline/classifier/experience, thử LTR nếu đủ dữ liệu; audit toàn pipeline. Chọn model trên validation rồi khóa và đánh giá test. Hoàn tất khi có Top 5 tách development/validation/test, phân tích lỗi, latency, missing data và lý do chọn model.

### Mốc 4 — API/UI demo

Triển khai mục 10, ownership, catalog/index/cache và trạng thái lỗi. Dùng PDF giả có text, JD demo hợp lệ. Hoàn tất khi CV mới ngoài pilot → trích xuất → ranking → hiển thị → xem JD/ứng tuyển, không cần sửa CSV bằng tay cho từng user.

### Mốc 5 — Nghiệm thu và báo cáo

Test quyền CV chéo user/JWT/role; PDF rỗng/scan/lỗi; JD đóng/hết hạn; phân trang; cache/version; timeout và dependency failure. Thêm E2E recommendation, chạy lại tests app và smoke trên VM. Báo cáo đúng phạm vi đã chạy, model/data versions và hạn chế; giữ trạng thái thử nghiệm nếu nhãn/test chưa đạt.

Đầu ra đề xuất: tài liệu data/model, manifest/split/config, package preprocessing–features–ranking, CLI train/evaluate, service/UI và tests. Có thể tổ chức thành `ml_data/`, `ml/`, `services/recommendation/`, `tests/ml/`, `docs/ml/`; **Mốc 0–2 đã thêm `ml_data/`, `tests/ml/` và `docs/ml/`; package `ml/` và service recommendation vẫn là đề xuất**. Không di chuyển hàng loạt file trước khi bảo toàn baseline.

## 12. Lệnh đối chiếu hiện tại

### Windows / VS Code — PowerShell cho ML

Chạy từ root `D:\JobApply`, dùng môi trường ML riêng đã được kiểm tra. Lệnh mặc định dùng cache E5 offline với revision/hash cố định; nếu thiếu cache thì xem hướng dẫn tải đúng revision trong [Mốc 0](docs/ml/baseline.md).

```powershell
Set-Location D:\JobApply
$mlPython = '.\jobapply_pilot_v1\.venv-embedding\Scripts\python.exe'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fffffff'
$baselineOut = ".\jobapply_pilot_v1\results\reruns\${runId}_baseline"
& $mlPython .\jobapply_pilot_v1\run_baseline.py --output $baselineOut --k 5
if ($LASTEXITCODE -ne 0) { throw 'Baseline failed; inspect the new run directory.' }
& $mlPython .\jobapply_pilot_v1\run_baseline.py --verify-run $baselineOut
```

Run có bản nhãn `labels_ai_draft.normalized.csv`; không sửa `judgments_ai_draft.csv`. Đánh giá CSV không cần tải E5 hay train:

```powershell
& $mlPython .\jobapply_pilot_v1\evaluate_topk.py --labels "$baselineOut\labels_ai_draft.normalized.csv" --rankings "$baselineOut\embedding_vs_bm25.csv" --k 5
& $mlPython -m unittest discover -s tests/ml -v
```

Các CLI train/evaluate yêu cầu truyền nhãn đã chuẩn hóa. `compare_embeddings.py`, trainer, BM25 và audit mặc định tạo thư mục run mới, từ chối thư mục đã tồn tại. `prepare_pilot.py` là công cụ dựng lại pilot cố định từ nguồn upstream, không chạy đè dữ liệu hiện có. `evaluate_topk.py` chỉ cần thư viện chuẩn Python.

Demo Top 5 dùng đúng model/input của một run hoàn tất, không fallback về model lịch sử:

```powershell
$selectedRun = '.\jobapply_pilot_v1\results\reruns\20261112_baseline_03'
& $mlPython .\jobapply_pilot_v1\jobapply_experience_v2\recommend.py --run-dir $selectedRun --cv-id CV_SYN_05
& $mlPython .\jobapply_pilot_v1\jobapply_experience_v2\recommend.py --run-dir $selectedRun --cv-text .\docs\ml\examples\cv_demo_synthetic.txt
```

Run đầy đủ không nằm trong Git; clone mới cần khôi phục kho run tin cậy hoặc chạy Mốc 0 vào thư mục mới rồi dùng đường dẫn đó. CV mới không cần có trong train; không truyền `--months` thì kinh nghiệm theo scope giữ unknown. Đây là demo model refit trên pilot, không phải metric held-out hoặc danh sách việc đang mở của app.

Kiểm kê ba CSV upstream, nhập kho JD chuẩn Mốc 2 và chọn lô 64 JD development (chỉ cần thư viện chuẩn Python, chi tiết tại [docs/ml/dataset_pipeline.md](docs/ml/dataset_pipeline.md)):

```powershell
$dataOut = ".\ml_data_runs\${runId}"
.\.venv\Scripts\python.exe -m ml_data inventory --output "$dataOut\inventory"
.\.venv\Scripts\python.exe -m ml_data upstream --source-dir . --output "$dataOut\upstream"
.\.venv\Scripts\python.exe -m ml_data verify --artifact "$dataOut\upstream"
```

### Linux VM / VMware — shell cho Docker

Tại root repo VM đã có .env và từng triển khai:

```sh
docker compose up -d --wait
docker compose ps
sh scripts/smoke-vm.sh http://127.0.0.1:8080
```

Lần đầu chuẩn bị .env theo [hướng dẫn VM](docs/deploy-vm.md), chạy `sh scripts/deploy-vm.sh first`; cập nhật theo hướng dẫn `update`. Không reset database/volume để thêm ML. Seed là bước riêng: `docker compose --profile tools run --build --rm seed`.

Demo local sau seed: `candidate@example.com`, `recruiter@example.com`, mật khẩu `DemoJobApply123!`. Windows truy cập `http://192.168.123.136:8080`. Nghiệp vụ/API/kiểm thử ở [tài liệu app](docs/application.md), [TESTING.md](TESTING.md). Mốc 0–2 chỉ chạy ML offline, không chạy lại Docker hoặc nghiệm thu recommendation.

## 13. Chỉ dẫn bàn giao cho Codex

> Đọc toàn bộ file được Git theo dõi, bắt đầu từ README và các nhóm ở mục 1. Xác minh trạng thái trước khi sửa code. Mục tiêu: upload/chọn CV và nhận Top 5 JD đang mở, preprocessing dùng chung offline/online. Tiếp tục từ dữ liệu Mốc 2 đã kiểm chứng, bổ sung CV mới theo hợp đồng schema, khóa split và triển khai parser/API/UI theo hợp đồng hiện có. Không chọn model bằng test, không coi pilot là bằng chứng chất lượng thực tế. Giữ ownership CV, snapshot ứng tuyển, service boundaries và dữ liệu VM. Mỗi PR ghi thay đổi, kiểm tra đã chạy, kết quả và phần thiếu. Lệnh Windows dùng PowerShell; shell Linux dùng trên VM.
