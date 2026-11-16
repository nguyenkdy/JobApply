"""Create an offline inspection page from existing scores; never fit or rescore."""
import argparse
from pathlib import Path
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml_data.common import csv_rows, file_hash, fresh_folder, read_json, require, seal, verify

SCRIPT = r"""'use strict';
const data = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; };
const names = {keyword:'Từ khóa', bm25:'BM25', e5:'E5-base', 'lr_text_C0.1':'LR: điểm văn bản', 'lr_metadata_C0.1':'LR: metadata — được chọn', lr_combined_C1:'LR: kết hợp', rule_proxy:'Bộ luật sinh nhãn — đối chiếu'};
const experienceKinds = {employment:'Làm việc', contract:'Hợp đồng', internship:'Thực tập', project:'Dự án', unknown:'Thiếu mốc kinh nghiệm'};
const fmt = v => v === null ? 'Không xác định' : Number(v).toFixed(4);
function detail(label, body) { const d=el('details'); d.append(el('summary',label),el('pre',body)); return d; }
function tags(parent, title, values) { const p=el('p'); p.append(el('strong', title + ': '),el('span',values.length ? values.join(', ') : 'Chưa có thông tin')); parent.append(p); }
function durations(value) { return Object.keys(value).length ? Object.entries(value).map(([scope,months]) => scope + ': ' + months + ' tháng').join('; ') : 'Chưa xác định — không phải 0 tháng'; }
for(const method of data.methods) { const o=el('option',names[method] || method); o.value=method; $('method').append(o); }
$('method').value=data.selected;
for(const cv of data.cvs) { const o=el('option',cv.external_id + ' · ' + cv.role + ' · ' + experienceKinds[cv.lineage.experience_kind]); o.value=cv.record_id; $('cv').append(o); }
for(const method of data.methods) { const m=data.metrics[method]; const tr=el('tr'); if(method===data.selected) tr.className='selected'; [names[method] || method,fmt(data.validation[method].ndcg5),fmt(m.ndcg5),fmt(m.recall5_ge2)].forEach(v=>tr.append(el('td',v))); $('comparison').append(tr); }
function render() {
 const cv=data.cvs.find(c=>c.record_id===$('cv').value), method=$('method').value;
 const m=data.byCV[method][cv.record_id];
 $('cvDetail').replaceChildren(el('h2',cv.external_id),el('p',cv.role + ' · ' + experienceKinds[cv.lineage.experience_kind],'muted'));
 tags($('cvDetail'),'Kỹ năng',cv.skills); tags($('cvDetail'),'Stack',cv.stack);
 $('cvDetail').append(el('p','Kinh nghiệm có ghi nhận: '+durations(cv.experience)),el('p','Họ template: '+cv.lineage.template_family,'muted'),detail('Đọc toàn bộ CV giả lập',cv.text_normalized));
 $('cvMetric').textContent='CV này: NDCG@5 '+fmt(m.ndcg5)+' · Recall@5 nhãn 2 '+fmt(m.recall5_ge2)+' · Có '+m.positives_ge2+'/50 JD nhãn 2.';
 const ranking=data.rankings[method][cv.record_id];
 const limit=$('full').checked ? 50 : 5;
 $('results').replaceChildren();
 ranking.slice(0,limit).forEach((r,i)=>{
  const jd=data.jobs[r.jd_id], label=data.labels[cv.record_id][r.jd_id], article=el('article',undefined,'job');
  const title=jd.text_normalized.split('\n').filter(Boolean).find(line=>line!=='Chức danh:') || jd.external_id;
  article.append(el('h3',(i+1)+'. '+title),el('span','Nhãn '+label.relevance_0_1_2,'badge grade'+label.relevance_0_1_2),el('span','Điểm '+Number(r.score).toFixed(6),'score'));
  article.append(el('p',jd.role+' · '+jd.external_id,'muted'));
  tags(article,'Skill chung',cv.skills.filter(s=>jd.skills.includes(s))); tags(article,'Stack chung',cv.stack.filter(s=>jd.stack.includes(s)));
  article.append(el('p','Ngưỡng kinh nghiệm đã trích xuất: '+durations(jd.experience)),detail('Đọc mô tả JD gốc dùng trong thí nghiệm',jd.text_normalized),detail('Lý do nhãn từ bộ luật (không phải lời giải thích của model)',label.rationale));
  $('results').append(article);
 });
 $('count').textContent=limit===5 ? 'Top 5 / 50 JD' : 'Toàn bộ 50 JD, theo thứ tự điểm';
}
['cv','method','full'].forEach(id=>$(id).addEventListener('change',render)); render();
"""

PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobApply — Xem kết quả Bước 4</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#172b3a;font:16px/1.6 'Segoe UI',Arial,sans-serif}main{max-width:1250px;margin:auto;padding:30px 24px 60px}h1{font-size:32px;line-height:1.2;margin:10px 0}h2{font-size:22px}h3{font-size:18px;margin:0 0 12px}h1,h2,h3{color:#12384b}.eyebrow{color:#14796d;font-weight:700;letter-spacing:.08em}.muted{color:#536574;font-size:14px}.notice{border-left:5px solid #b57413;background:#fff8e8;padding:15px 20px;border-radius:8px}.card,.job{background:white;border:1px solid #dce4ec;border-radius:12px;padding:20px;margin:16px 0;box-shadow:0 2px 8px #10203005}.grid{display:grid;grid-template-columns:360px 1fr;gap:24px;align-items:start}.controls{display:grid;grid-template-columns:1fr 1fr;gap:20px}label{display:block;font-weight:600}select{width:100%;padding:12px;border:1px solid #a9bac8;border-radius:7px;background:white;font:inherit;color:#163d51;margin-top:6px}select:focus,summary:focus{outline:3px solid #55a7bd}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #e2e9ee}th{background:#eff5f8}.selected{background:#e6f5ef;font-weight:600}.table{overflow:auto}.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-weight:700;background:#e8edf3;margin-right:12px}.grade2{color:#0d6756;background:#e4f5ec}.grade1{color:#775212;background:#fff2ce}.grade0{color:#963c37;background:#ffedeb}.score{font-variant-numeric:tabular-nums;font-size:14px;color:#425c6b}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 'Segoe UI',Arial,sans-serif;background:#f6f8fa;padding:14px;border-radius:6px}summary{cursor:pointer;color:#145f83;font-weight:600;padding:8px 0}input{width:18px;height:18px;vertical-align:middle}p{margin:9px 0}.footer{margin-top:30px;color:#536574;font-size:13px}@media(max-width:850px){.grid,.controls{grid-template-columns:1fr}main{padding:20px 14px}h1{font-size:26px}}
</style><script id="data" type="application/json">__DATA__</script><script src="viewer.js" defer></script></head><body><main>
<div class="eyebrow">JOBAPPLY · KẾT QUẢ ĐÃ LƯU · 14/11/2026</div><h1>Bước 4: kiểm tra model đã đề xuất gì</h1>
<p>Train: 30 CV × 50 JD. Validation: 15 CV × 50 JD. Test: 15 CV × 50 JD. Trang này hiển thị <strong>kết quả test đã có</strong>; thay lựa chọn chỉ đổi cách xem, không huấn luyện hoặc chấm lại.</p>
<p class="notice"><strong>NDCG = 1 không phải chất lượng tuyển dụng 100%.</strong> CV đều giả lập; nhãn 0/1/2 do bộ luật nghề, stack và kinh nghiệm tạo ra. Model metadata có thể học lại bộ luật này. Đây chưa phải kiểm chứng trên ứng viên thật.</p>
<section class="card"><h2>So sánh các phương pháp</h2><p>Model chọn bằng validation: <strong>LR metadata, C = 0,1</strong>. Cấu hình kết hợp hòa điểm; quy tắc đã khóa ưu tiên model đơn giản hơn. Baseline luật chỉ để đối chiếu, không tham gia chọn model.</p><div class="table"><table><thead><tr><th>Phương pháp</th><th>NDCG@5 validation</th><th>NDCG@5 test</th><th>Recall@5 test, nhãn 2</th></tr></thead><tbody id="comparison"></tbody></table></div><p class="muted">NDCG: thứ tự đề xuất gần thứ tự lý tưởng theo nhãn đến đâu (cao hơn tốt hơn). Recall nhãn 2: tìm được bao nhiêu JD nhãn 2 trong Top 5; chỉ tính trung bình trên 6/15 CV có positive. 9 CV còn lại không xác định. Trần Recall@5 của tập này là 0,9444 vì hai CV có sáu JD nhãn 2.</p></section>
<section class="card controls"><label>1. Chọn CV test<select id="cv"></select></label><label>2. Chọn phương pháp<select id="method"></select></label></section>
<p id="cvMetric" class="notice"></p><div class="grid"><aside><section id="cvDetail" class="card"></section><section class="card"><h2>Cách đọc kết quả</h2><p><strong>Nhãn 2:</strong> đạt bộ tiêu chí proxy về nghề, stack và thời lượng đã trích xuất.</p><p><strong>Nhãn 1:</strong> tương thích một phần theo nghề, còn thiếu/khác thông tin.</p><p><strong>Nhãn 0:</strong> khác nghề chính theo taxonomy đang dùng.</p><p>Điểm model dùng để sắp thứ tự, không phải xác suất được tuyển. Điểm BM25, E5 và LR có thang khác nhau; không so trực tiếp giá trị điểm giữa chúng.</p><p>Đọc nội dung CV/JD để tự kiểm tra các trường hợp cùng từ khóa nhưng khác stack hoặc yêu cầu. Lý do nhãn là bằng chứng của bộ luật, không phải lời giải thích nhân quả của LR.</p></section></aside><section><h2 id="count"></h2><label><input id="full" type="checkbox"> Xem cả 50 JD để kiểm tra những tin ngoài Top 5</label><div id="results"></div></section></div>
<p class="footer">Trang offline, không có kết nối ngoài hoặc API. Nguồn: run 20261114_step4_v1_01; manifest nguồn __HASH__. Không thay dữ liệu, nhãn, split hoặc model. Tất cả hồ sơ CV là synthetic.</p>
</main></body></html>"""


def build(run, output):
    run = Path(run).resolve()
    verify(run, "step4-experiment")
    before = file_hash(run / "manifest.json")
    summary, docs, metrics = (read_json(run / name) for name in ("summary.json", "documents.json", "test.json"))
    predictions = csv_rows(run / "test_predictions.csv")[1]
    labels = {}
    for row in csv_rows(run / "inputs/test_labels.csv")[1]:
        labels.setdefault(row["cv_id"], {})[row["jd_id"]] = {k: row[k] for k in ("relevance_0_1_2", "rationale")}
    by_cv = {method: {r["cv_id"]: r for r in result["by_cv"]} for method, result in metrics.items()}
    rankings = {method: {cv: [] for cv in by_cv[method]} for method in metrics}
    for r in predictions:
        score = float(r["score"])
        require(math.isfinite(score) and r["relevance"] == labels[r["cv_id"]][r["jd_id"]]["relevance_0_1_2"], "Prediction/label mismatch")
        rankings[r["method"]][r["cv_id"]].append(dict(jd_id=r["jd_id"], score=score))
    for method, queries in rankings.items():
        for cv_id, ranking in queries.items():
            ranking.sort(key=lambda r: (-r["score"], r["jd_id"]))
            require(len(ranking) == len({r["jd_id"] for r in ranking}) == 50, "Incomplete catalogue")
            require([r["jd_id"] for r in ranking[:5]] == by_cv[method][cv_id]["top5"], "Top5 differs from saved evaluation")
    cvs = sorted((docs[c] for c in labels), key=lambda r: (r["role"], r["external_id"]))
    require(len(cvs) == 15 and len(predictions) == 15*50*len(metrics), "Unexpected test size")
    data = dict(selected=summary["selected"]["name"], methods=list(metrics), cvs=cvs,
        jobs={k: v for k, v in docs.items() if v["kind"] == "jd"},
        metrics=summary["test_comparison"], validation=summary["validation_comparison"],
        byCV=by_cv, rankings=rankings, labels=labels)
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    folder = fresh_folder(output, (run,))
    (folder / "index.html").write_text(PAGE.replace("__DATA__", encoded).replace("__HASH__", before), encoding="utf-8")
    (folder / "viewer.js").write_text(SCRIPT, encoding="utf-8")
    seal(folder, "step4-viewer", dict(input_run_manifest_sha256=before, cv_count=15, jd_count=50,
        methods=len(metrics), prediction_rows=len(predictions), all_top5_match_saved_metrics=True, no_rescoring=True))
    require(file_hash(run / "manifest.json") == before, "Input changed")
    print(folder / "index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.run, args.output)
