#!/usr/bin/env python3
"""Run transparent keyword and BM25 baselines. Standard library, Python 3.9+.

python run_bm25.py --jobs jobs_pilot.csv --cvs cvs_synthetic.csv --output-dir results
python run_bm25.py --jobs jobs_pilot.csv --cv-text synthetic_cv_texts/CV_SYN_01.txt
"""
import argparse
import csv
import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from baseline_common import catalog, new_run_path, validate_k

VERSION="1.0.0"
STOP_WORDS=set("""a an the and or of to for in on at by with as is are be been being was were
this that these those it its your you we our their they have has had can will would should
from into through such than also both other more all any using use used must least
và hoặc có các những một với trong của cho là được đã từ đến như theo trên để bằng
này đó tôi bạn chúng tôi cần sẽ về khi nếu thì cùng mỗi nhiều việc tốt khả năng kỹ
năm years year experience kinh nghiệm chức danh nhiệm vụ yêu cầu ưu tiên nice to""".split())
ALIASES=[
    (r"\breact(?:\.?js| js)\b","react"), (r"\bnode(?:js| js)\b","node.js"),
    (r"\bnext(?:js| js)\b","next.js"), (r"\bvue(?:js| js)\b","vue.js"),
    (r"\bgolang\b","go"), (r"\bpostgres\b","postgresql"),
    (r"\bpower\s*bi\b","powerbi"), (r"\bspring\s*boot\b","springboot"),
    (r"\bback[- ]end\b","backend"), (r"\bfront[- ]end\b","frontend"),
    (r"\bci\s*[/ -]\s*cd\b","ci/cd"), (r"\bk8s\b","kubernetes"),
    (r"\brestful\b","rest"), (r"\bapis\b","api"),
]
TOKEN=re.compile(r"(?<!\w)(?:c\+\+|c#|f#|\.net|ci/cd)(?!\w)|[^\W_]+(?:[.+#/][^\W_]+)*",re.UNICODE)


def tokenize(text):
    text=unicodedata.normalize("NFC",text).casefold()
    for pattern,replacement in ALIASES:text=re.sub(pattern,replacement,text)
    return [t for t in TOKEN.findall(text) if t not in STOP_WORDS]


class BM25:
    """Positive-IDF BM25, k1=1.5, b=0.75. Each unique query term counts once."""
    def __init__(self,texts,k1=1.5,b=0.75):
        if not texts:raise ValueError("No documents")
        if k1<=0 or not 0<=b<=1:raise ValueError("Invalid BM25 parameters")
        self.k1,self.b=k1,b
        self.tf=[Counter(tokenize(t)) for t in texts]
        self.lengths=[sum(c.values()) for c in self.tf]
        self.avgdl=sum(self.lengths)/len(texts)
        if not self.avgdl:raise ValueError("Documents have no tokens")
        df=Counter(t for counts in self.tf for t in counts)
        n=len(texts)
        self.idf={t:math.log(1+(n-frequency+0.5)/(frequency+0.5)) for t,frequency in df.items()}

    def score(self,query):
        query=set(tokenize(query))
        results=[]
        for counts,dl in zip(self.tf,self.lengths):
            norm=self.k1*(1-self.b+self.b*dl/self.avgdl)
            terms={t:self.idf[t]*(counts[t]*(self.k1+1))/(counts[t]+norm)
                   for t in sorted(query) if counts[t]}
            results.append({"bm25_score":math.fsum(terms.values()),
                "keyword_overlap_count":len(terms),"contributions":terms})
        return results


def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def write_csv(path,records,fields=None):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields or list(records[0]));w.writeheader();w.writerows(records)


def run(jobs,cvs,top_k=5):
    index=BM25([r["match_text"] for r in jobs])
    full=[]
    for cv in cvs:
        scores=index.score(cv["cv_text"])
        order=sorted(range(len(jobs)),key=lambda i:(-scores[i]["bm25_score"],jobs[i]["job_id"]))
        keyword_order=sorted(range(len(jobs)),key=lambda i:(-scores[i]["keyword_overlap_count"],jobs[i]["job_id"]))
        keyword_rank={i:rank for rank,i in enumerate(keyword_order,1)}
        for rank,i in enumerate(order,1):
            job,score=jobs[i],scores[i]
            terms=sorted(score["contributions"].items(),key=lambda p:(-p[1],p[0]))[:10]
            full.append({"cv_id":cv["cv_id"],"rank_bm25":rank,"job_id":job["job_id"],"title":job["title_for_matching"],
                "bm25_score":round(score["bm25_score"],6),"rank_keyword":keyword_rank[i],
                "keyword_overlap_count":score["keyword_overlap_count"],
                "top_matching_terms":", ".join(t for t,_ in terms),
                "term_contributions_json":json.dumps({t:round(s,6) for t,s in terms},ensure_ascii=False),
                "pilot_group":job.get("pilot_group",""),"site":job.get("site",""),"job_url":job.get("job_url","")})
    return full,[r for r in full if r["rank_bm25"]<=top_k and r["bm25_score"]>0]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs",type=Path,default=Path("jobs_pilot.csv"))
    inputs=ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--cvs",type=Path)
    inputs.add_argument("--cv-text",type=Path)
    ap.add_argument("--top-k",type=int,default=5)
    ap.add_argument("--output-dir",type=Path,default=new_run_path(Path.cwd(), "bm25"))
    args=ap.parse_args()
    if args.top_k<1:ap.error("top-k must be positive")
    jobs=catalog(args.jobs, "job_id", "match_text")
    cvs=catalog(args.cvs, "cv_id", "cv_text") if args.cvs else [{"cv_id":args.cv_text.stem,"cv_text":args.cv_text.read_text(encoding="utf-8-sig")}]
    validate_k(args.top_k, len(jobs))
    if not jobs or not cvs:ap.error("Empty input")
    if len({r['job_id'] for r in jobs})!=len(jobs):ap.error("Duplicate job_id")
    if len({r['cv_id'] for r in cvs})!=len(cvs):ap.error("Duplicate cv_id")
    if any(not r.get('match_text','').strip() for r in jobs):ap.error("A JD has empty match_text")
    if any(not tokenize(r.get('cv_text','')) for r in cvs):ap.error("A CV has no usable tokens")
    all_rows,top=run(jobs,cvs,args.top_k)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    write_csv(args.output_dir/"rankings_all.csv",all_rows)
    write_csv(args.output_dir/"top_matches.csv",top,list(all_rows[0]))
    report={"algorithm":"BM25_positive_idf","version":VERSION,"k1":1.5,"b":0.75,
        "jobs":len(jobs),"cvs":len(cvs),"top_k":args.top_k,
        "jobs_sha256":hashlib.sha256(args.jobs.read_bytes()).hexdigest(),
        "cvs_sha256":hashlib.sha256((args.cvs or args.cv_text).read_bytes()).hexdigest(),
        "features":["match_text","cv_text"],
        "not_used_as_features":["pilot_group","site","company","job_id","cv_id","job_url","target_role","experience_months"],
        "metrics":{"recall_at_k":None,"ndcg_at_k":None},
        "metrics_status":"not_computed_no_human_relevance_labels",
        "score_is_probability":False,"embedding_run":False,"supervised_training_run":False}
    (args.output_dir/"run_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    # Blank, shuffled judgments avoid presenting model scores as annotation targets.
    judgments=[{"cv_id":cv['cv_id'],"job_id":job['job_id'],"relevance_0_1_2":"","reviewer":"","rationale":""}
               for cv in cvs for job in jobs]
    random.Random(20261104).shuffle(judgments)
    template=args.output_dir/"judgments_template.csv"
    # Preserve any human work when the baseline is rerun.
    if not template.exists():write_csv(template,judgments)
    for cv in cvs:
        print('\n'+cv['cv_id'])
        if not any(r['cv_id']==cv['cv_id'] for r in top):
            print('No shared terms after preprocessing; no positive-score results.')
        for r in top:
            if r['cv_id']==cv['cv_id']:print(f"{r['rank_bm25']}. {r['title']} | BM25={r['bm25_score']:.3f}")


if __name__=="__main__":main()
