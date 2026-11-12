#!/usr/bin/env python3
"""Synthetic input perturbations; this is not a formal fairness certification."""
import argparse
import json
from pathlib import Path
from run_bm25 import BM25, read_csv, write_csv
from baseline_common import new_run_path

PAIRS={
    "gender":("Giới tính: Nam.","Giới tính: Nữ."),
    "age":("Tuổi: 24.","Tuổi: 45."),
    "address":("Địa chỉ: Hà Nội.","Địa chỉ: Hồ Chí Minh."),
    "name":("Họ tên: Nguyễn Minh Anh.","Họ tên: Trần Thu Hà."),
    "school_name_proxy":("Học vấn: Cử nhân Công nghệ thông tin. Trường: Đại học Bách Khoa.",
                         "Học vấn: Cử nhân Công nghệ thông tin. Trường: Đại học Kinh tế."),
}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs",type=Path,default=Path("jobs_pilot.csv"))
    ap.add_argument("--cvs",type=Path,default=Path("cvs_synthetic.csv"))
    ap.add_argument("--output-dir",type=Path,default=new_run_path(Path.cwd(), "audit"))
    args=ap.parse_args()
    jobs,cvs=read_csv(args.jobs),read_csv(args.cvs)
    index=BM25([r["match_text"] for r in jobs])
    def rank(text):
        scores=[x["bm25_score"] for x in index.score(text)]
        order=sorted(range(len(jobs)),key=lambda i:(-scores[i],jobs[i]["job_id"]))
        return scores,order
    rows=[]
    for cv in cvs:
        baseline,_=rank(cv["cv_text"])
        for facet,(a,b) in PAIRS.items():
            # Actual pipeline uses cv_text only. Additional metadata does not enter the scorer.
            va,vb=dict(cv),dict(cv)
            va["sensitive_metadata"]=a;vb["sensitive_metadata"]=b
            sa,oa=rank(va["cv_text"]);sb,ob=rank(vb["cv_text"])
            assert sa==sb==baseline
            # Stress test an unsafe integration that blindly concatenates raw CV text.
            raw_a,order_a=rank(cv["cv_text"]+"\n"+a)
            raw_b,order_b=rank(cv["cv_text"]+"\n"+b)
            ra={i:r for r,i in enumerate(order_a,1)};rb={i:r for r,i in enumerate(order_b,1)}
            rows.append({"cv_id":cv["cv_id"],"facet":facet,"synthetic_variant_a":a,"synthetic_variant_b":b,
                "metadata_excluded_scores_identical":True,
                "raw_text_top5_order_changed":order_a[:5]!=order_b[:5],
                "raw_text_top5_set_changed":set(order_a[:5])!=set(order_b[:5]),
                "raw_text_top1_changed":order_a[0]!=order_b[0],
                "raw_text_max_rank_change":max(abs(ra[i]-rb[i]) for i in ra),
                "raw_text_max_score_change":round(max(abs(x-y) for x,y in zip(raw_a,raw_b)),6)})
    args.output_dir.mkdir(parents=True,exist_ok=False)
    write_csv(args.output_dir/"fairness_probe.csv",rows)
    summary={"scope":"synthetic_perturbation_only_not_fairness_certification","pairs":len(rows),
        "metadata_excluded_invariance_passes":len(rows),
        "raw_cv_text_pairs_with_top5_order_change":sum(r['raw_text_top5_order_changed'] for r in rows),
        "raw_cv_text_pairs_with_top1_change":sum(r['raw_text_top1_changed'] for r in rows),
        "by_facet":{f:{"top5_order_changed":sum(r['raw_text_top5_order_changed'] for r in rows if r['facet']==f),
                       "pairs":sum(r['facet']==f for r in rows)} for f in PAIRS},
        "limitations":["No PDF parsing or automatic anonymization is implemented.",
            "Metadata invariance only tests the current field allowlist.",
            "A zero change on these samples does not imply no discrimination or proxy leakage.",
            "The school probe changes the institution while holding degree and field constant.",
            "Do not include personal metadata when constructing cv_text for real use."]}
    (args.output_dir/"audit_report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
