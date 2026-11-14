"""Label-free features, train-only fitting and explicit ranking metrics."""
from collections import Counter, defaultdict
import math

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml_data.common import require
from ml_data.label_rules import ROLE_SCOPES

TEXT_FEATURES = ("bm25", "e5")
META_FEATURES = ("role_equal", "role_known", "skill_coverage", "stack_coverage",
                 "skill_known", "stack_known", "experience_coverage", "experience_gap_years",
                 "jd_experience_known", "cv_experience_comparable", "strict_bound_violation")
FEATURE_SETS = dict(text=TEXT_FEATURES, metadata=META_FEATURES, combined=TEXT_FEATURES + META_FEATURES)
C_VALUES = (0.1, 1.0, 10.0)


def professional_view(record):
    """Allowlist for all scoring. Personal data and pair labels are never inputs."""
    return dict(text=record["text_normalized"], role=record.get("role", ""),
                skills=record.get("skills", []), stack=record.get("stack", []),
                experience=record.get("experience", {}),
                experience_kind=record.get("lineage", {}).get("experience_kind", "unknown"))


def metadata_features(cv, jd, receipt):
    cv, jd = professional_view(cv), professional_view(jd)
    def coverage(field):
        target = set(jd[field])
        return len(set(cv[field]) & target) / len(target) if target else 0.0
    comparable = cv["experience_kind"] in {"employment", "contract"}
    observed, required = cv["experience"], jd["experience"]
    matched, gaps, violations = 0, [], []
    if comparable:
        for scope, need in required.items():
            aliases = next((s for s in ROLE_SCOPES.values() if scope in s), {scope})
            values = [observed[s] for s in aliases if s in observed]
            if not values:
                continue
            actual = max(values)
            matched += 1
            gaps.append(max(0, need - actual) / 12)
            strict = any(e.get("strictly_greater") and e.get("threshold_months") == need
                         and aliases & set(e.get("scopes", [])) for e in receipt.get("experience_evidence", []))
            violations.append(strict and actual <= need)
    return dict(role_equal=float(bool(cv["role"] and jd["role"]) and cv["role"].casefold() == jd["role"].casefold()),
        role_known=float(bool(cv["role"] and jd["role"])), skill_coverage=coverage("skills"), stack_coverage=coverage("stack"),
        skill_known=float(bool(cv["skills"] and jd["skills"])), stack_known=float(bool(cv["stack"] and jd["stack"])),
        experience_coverage=matched / len(required) if required else 0.0,
        experience_gap_years=max(gaps, default=0.0), jd_experience_known=float(bool(required)),
        cv_experience_comparable=float(comparable and bool(observed)), strict_bound_violation=float(any(violations)))


def feature_matrix(rows, names):
    result = np.array([[r[f] for f in names] for r in rows], dtype=np.float64)
    require(result.ndim == 2 and result.shape[1] == len(names) and np.isfinite(result).all(), "Invalid features")
    return result


def fit_classifier(rows, labels, names, c):
    require(len(rows) == len(labels) and set(labels) == {0, 1, 2}, "Train requires all three proxy classes")
    model = make_pipeline(StandardScaler(), LogisticRegression(C=c, class_weight="balanced", solver="lbfgs",
        max_iter=3000, tol=1e-8, random_state=20261113))
    model.fit(feature_matrix(rows, names), np.asarray(labels))
    require(max(model[-1].n_iter_) < model[-1].max_iter, "Classifier did not converge")
    return model


def expected_relevance(model, rows, names):
    return model.predict_proba(feature_matrix(rows, names)) @ model.classes_.astype(float)


def rank_metrics(job_ids, labels, scores, k=5):
    require(len(job_ids) == len(set(job_ids)) == len(labels) == len(scores) and len(job_ids) >= k,
            "Incomplete/duplicate ranking catalogue")
    require(set(labels) <= {0, 1, 2} and all(math.isfinite(float(s)) for s in scores), "Invalid label or score")
    order = sorted(range(len(job_ids)), key=lambda i: (-float(scores[i]), job_ids[i]))
    def dcg(grades):
        return math.fsum((2 ** int(g)-1) / math.log2(i+2) for i, g in enumerate(grades[:k]))
    ideal = dcg(sorted(labels, reverse=True))
    positives = {t: sum(g >= t for g in labels) for t in (1, 2)}
    result = dict(ndcg5=dcg([labels[i] for i in order]) / ideal if ideal else None)
    for t in (1, 2):
        hits = sum(labels[i] >= t for i in order[:k])
        result[f"recall5_ge{t}"] = hits / positives[t] if positives[t] else None
        result[f"positives_ge{t}"] = positives[t]
    result["top5"] = [job_ids[i] for i in order[:k]]
    return result


def aggregate(per_cv):
    result = dict(cv_count=len(per_cv))
    for metric in ("ndcg5", "recall5_ge1", "recall5_ge2"):
        values = [r[metric] for r in per_cv if r[metric] is not None]
        result[metric] = math.fsum(values) / len(values) if values else None
        result[metric + "_defined"] = len(values)
        result[metric + "_undefined"] = len(per_cv)-len(values)
    return result


def evaluate(rows, labels, scores, records):
    require(len(rows) == len(labels) == len(scores), "Score alignment mismatch")
    grouped = defaultdict(list)
    for r, y, score in zip(rows, labels, scores):
        grouped[r["cv_id"]].append((r["jd_id"], int(y), float(score)))
    by_cv = []
    for cv_id, entries in sorted(grouped.items()):
        cv = records[cv_id]
        result = rank_metrics([e[0] for e in entries], [e[1] for e in entries], [e[2] for e in entries])
        by_cv.append(dict(cv_id=cv_id, role=cv["role"], experience_kind=cv["lineage"]["experience_kind"],
                          template_family=cv["lineage"]["template_family"], group_id=cv["group_id"], **result))
    slices = {field: {value: aggregate([r for r in by_cv if r[field] == value]) for value in sorted({r[field] for r in by_cv})}
              for field in ("role", "experience_kind", "template_family")}
    return dict(macro=aggregate(by_cv), by_cv=by_cv, slices=slices,
                class_counts=dict(Counter(str(y) for y in labels)))


def selection_key(item):
    """Predeclared tie order: NDCG, strict recall, simpler family, smaller C, ID."""
    return (-round(item["metrics"]["macro"]["ndcg5"], 12),
            -round(item["metrics"]["macro"]["recall5_ge2"] or 0, 12),
            item["complexity"], item.get("c", 0), item["name"])


def select_validation(candidates):
    eligible = [c for c in candidates if c["family"] != "rule_proxy"]
    require(eligible, "No independent candidate methods")
    return min(eligible, key=selection_key)
