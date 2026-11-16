"""Bounded technical proxy labels for the expanded taxonomy; abstention is a result.

No model scores, gold claims, absence-as-negative, title-mismatch negatives or
generic-to-technology duration conversion. Freeze this version before label runs.
"""
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from .common import (ROOT, csv_rows, digest, file_hash, fresh_folder, read_json, read_lines,
                     require, seal, verify, write_csv, write_json, write_lines)
from .intake import check_intake, occupation_relation

VERSION = "expanded-technical-proxy-v1"
POLICY = dict(version=VERSION, label_kind="automatic_rule_proxy", target="bounded_technical_compatibility_not_hiring_suitability",
    label_0="Explicit CV non-use contradicts a complete mandatory technology clause, or comparable explicit duration is below a complete minimum clause",
    label_1="Same/overlapping occupation and shared affirmative core technology; incomplete conditions do not imply full fit",
    label_2="Same occupation, every observed technical clause parsed as mandatory/preferred, mandatory clauses supported, explicit professional duration bounds satisfied",
    missing="insufficient_evidence with empty label; never zero", unknown_occupation="abstain",
    negative_skill="Only a complete explicit non-use clause, not missing skill metadata",
    duration="Exact scope, employment/contract only; explicit simple lower bounds; no total-to-technology inference",
    unsupported_logic="Abstain on clause satisfaction; cannot justify 0 or 2",
    unparsed_soft_requirements="Not evaluated: education/language/personality/domain constraints remain outside the technical proxy",
    holdout="Same frozen policy for every partition; no ranking input, no rule tuning from holdout label distribution",
    final_test_ready=False, independent_gold=False)

OPTIONAL = re.compile(r"ưu\s+tiên|không\s+bắt\s+buộc|không\s+yêu\s+cầu|không\s+cần|lợi\s+thế|preferred|optional|nice\s+to|not\s+required|advantage|no\s+experience", re.I)
REQUIRED = re.compile(r"^(?:bắt buộc(?: phải)?(?: có)?(?: (?:kinh nghiệm|kiến thức)(?: (?:về|với))?)?|yêu cầu(?: sử dụng)?|must (?:know|have experience (?:with|in))|required(?: skills)?|proficient (?:in|with)|thành thạo|sử dụng thành thạo)\s*:?\s+(.+?)\.?$", re.I)
EXPERIENCE_CUE = re.compile(r"\d\s*(?:năm|tháng|years?|months?)\b", re.I)
CONDITIONAL = re.compile(r"\b(?:nếu|if|either|depending)\b|một trong|one of|tùy theo|tuỳ theo|junior.*senior|senior.*junior", re.I | re.S)
SCOPES = {"kinh nghiệm nghề nghiệp": "professional experience", "professional experience": "professional experience",
          "kinh nghiệm phát triển phần mềm": "software development", "software development experience": "software development",
          "kinh nghiệm kiểm thử phần mềm": "kiểm thử phần mềm", "software testing experience": "kiểm thử phần mềm",
          **{f"kinh nghiệm {t}": t for t in ("python", "java", "react", "django", "aws", "selenium", "kubernetes", "sql", "frontend", "devops")},
          **{f"experience with {t}": t for t in ("python", "java", "react", "django", "aws", "selenium", "kubernetes", "sql")}}


def clean_clause(text):
    return re.sub(r"\s+", " ", text).strip().lstrip("-•* ").rstrip(". ")


def mandatory_clause(quote, terms, field="requirements_text"):
    """Only accept a complete simple term expression; surrounding prose can change logic."""
    if field == "preferred_requirements_text" or OPTIONAL.search(quote):
        return dict(state="preferred", terms=terms)
    match = REQUIRED.fullmatch(clean_clause(quote))
    if not match or not terms:
        return dict(state="unresolved", terms=terms)
    expression = match[1].strip().rstrip(".").casefold()
    keys = sorted(set(t.casefold() for t in terms), key=lambda t: (-len(t), t))
    for i, term in enumerate(keys):
        expression = re.sub(r"(?<!\w)" + re.escape(term) + r"(?!\w)", f"T{i}", expression, flags=re.I)
    # No commas/slashes or flat lists: AND/OR scope cannot be guessed.
    if re.fullmatch(r"T\d+", expression):
        op = "single"
    elif re.fullmatch(r"T\d+(?:\s+(?:và|and)\s+T\d+)+", expression, re.I):
        op = "all_of"
    elif re.fullmatch(r"T\d+(?:\s+(?:hoặc|or)\s+T\d+)+", expression, re.I):
        op = "any_of"
    else:
        return dict(state="unresolved", terms=terms)
    used = [keys[int(i)] for i in re.findall(r"T(\d+)", expression)]
    return dict(state="mandatory", operator=op, terms=used)


def duration_clause(quote):
    """Deliberately small grammar; no fallback from 'similar position' to total months."""
    text = clean_clause(quote).casefold()
    if OPTIONAL.search(text):
        return None
    pattern = (r"(?:yêu cầu\s+|có\s+)?(?P<bound>ít nhất|tối thiểu|từ|trên|at least|minimum(?: of)?|more than)?\s*"
               r"(?P<n>\d+)\s*(?P<unit>năm|tháng|years?|months?)\s+(?:of\s+)?(?P<scope>.+?)(?:\s+trở lên)?")
    m = re.fullmatch(pattern, text)
    if not m or m["scope"] not in SCOPES or not (m["bound"] or text.endswith("trở lên")):
        return None
    months = int(m["n"]) * (12 if m["unit"] in {"năm", "year", "years"} else 1)
    if months <= 0:
        return None
    return dict(scope=SCOPES[m["scope"]], months=months, strict=m["bound"] in {"trên", "more than"})


def explicit_nonuse(text, vocabulary):
    result = {}
    for match in re.finditer(r"[^\n;.!?]+", text):
        clause = clean_clause(match[0])
        for term in vocabulary:
            pattern = (r"(?:tôi\s+)?(?:chưa (?:từng )?(?:sử dụng|dùng)|không có kinh nghiệm (?:với|về)|"
                       r"(?:i )?have not used|no experience with)\s+" + re.escape(term))
            if re.fullmatch(pattern, clause, re.I):
                result[term.casefold()] = dict(quote=match[0], start=match.start(), end=match.end())
    return result


def source_field(record, name):
    rows = [o["raw_row"] for o in record["occurrences"] if name in o["raw_row"]]
    require(rows, "JD evidence source field missing")
    return rows[0][name]


def jd_facts(record, receipt):
    require(receipt["job_id"] == record["external_id"], "JD evidence identity mismatch")
    def checked(span):
        value = source_field(record, span["field"])
        require(value[span["start"]:span["end"]] == span["quote"], "JD literal evidence mismatch")
        return {k: span[k] for k in ("field", "start", "end", "quote")}
    role_evidence = [checked(e) for e in receipt.get("role_evidence", [])]
    skills = {}
    for term, e in receipt.get("skill_evidence", {}).items():
        checked(e)
        field = source_field(record, e["field"])
        line = field[field.rfind("\n", 0, e["start"])+1:field.find("\n", e["end"]) if "\n" in field[e["end"]:] else len(field)]
        if not OPTIONAL.search(line) and not re.search(r"\b(?:chưa|không|not|without)\b", line, re.I):
            skills[term.casefold()] = checked(e)
    clauses = []
    for item in receipt.get("requirement_clauses", []):
        parsed = mandatory_clause(item["quote"], item["terms"], item["field"])
        if parsed["state"] == "unresolved" and duration_clause(item["quote"]):
            parsed["state"] = "duration_condition"
        clauses.append(dict(**parsed, evidence=checked(item)))
    durations, unresolved_durations = [], []
    text = source_field(record, "requirements_text")
    for m in re.finditer(r"[^\n;]+", text):
        if not EXPERIENCE_CUE.search(m[0]) or OPTIONAL.search(m[0]):
            continue
        evidence = dict(field="requirements_text", start=m.start(), end=m.end(), quote=m[0])
        parsed = duration_clause(m[0])
        if parsed:
            durations.append(dict(**parsed, evidence=evidence))
        else:
            unresolved_durations.append(evidence)
    # Cross-line alternatives and multiple levels need a richer parser. A local
    # 'mandatory' phrase alone cannot prove a condition applies to every applicant.
    if CONDITIONAL.search(text) or len(durations) > 1:
        for clause in clauses:
            if clause["state"] in {"mandatory", "duration_condition"}:
                clause["state"] = "unresolved"
        unresolved_durations.extend(d["evidence"] for d in durations)
        durations = []
    return dict(role=record["role"], role_precision=record.get("role_precision"), benchmark_scope=record.get("benchmark_scope"),
                role_evidence=role_evidence, skills=skills, clauses=clauses, durations=durations,
                unresolved_durations=unresolved_durations, text_sha256=record["text_sha256"],
                evidence_sha256=digest(json.dumps(receipt, ensure_ascii=False, sort_keys=True)))


def cv_facts(record, receipt, vocabulary):
    text = record["text_original"]
    require(receipt["cv_id"] == record["external_id"] and receipt["text_sha256"] == digest(text), "CV receipt identity/hash mismatch")
    for span in [*receipt["skills"].values(), *receipt["durations"]]:
        require(text[span["start"]:span["end"]] == span["quote"], "CV literal evidence mismatch")
    positive = {k.casefold(): v for k, v in receipt["skills"].items()}
    negative = explicit_nonuse(text, vocabulary)
    require(not set(positive) & set(negative), "Conflicting positive/negative CV skill assertions")
    require(set(record["skills"]) == set(positive), "CV imported skills differ from evidence")
    require(record["experience"] == {d["scope"].casefold(): d["months"] for d in receipt["durations"]}, "CV duration metadata differs from evidence")
    return dict(role=record["role"], skills=positive, nonuse=negative, durations=receipt["durations"],
                experience_kind=record["lineage"]["experience_kind"], text_sha256=record["text_sha256"])


def judge(cv, jd):
    """Pure deterministic policy: facts in, evidence references and proxy decision out."""
    relation = occupation_relation(cv["role"], jd["role"])["state"]
    common = sorted(set(cv["skills"]) & set(jd["skills"]))
    outcomes = []
    for index, clause in enumerate(jd["clauses"]):
        if clause["state"] != "mandatory":
            continue
        states = ["yes" if t in cv["skills"] else "no" if t in cv["nonuse"] else "unknown" for t in clause["terms"]]
        if clause["operator"] == "any_of":
            state = "yes" if "yes" in states else "no" if all(s == "no" for s in states) else "unknown"
        else:
            state = "no" if "no" in states else "yes" if all(s == "yes" for s in states) else "unknown"
        outcomes.append(dict(clause=index, state=state, term_states=dict(zip(clause["terms"], states))))
    duration_states = []
    for index, bound in enumerate(jd["durations"]):
        matching = [d for d in cv["durations"] if d["scope"].casefold() == bound["scope"] and
                    d["kind"] in {"employment", "contract"}]
        state = "unknown"
        if matching:
            value = max(d["months"] for d in matching)
            state = "yes" if value > bound["months"] or (value == bound["months"] and not bound["strict"]) else "no"
        duration_states.append(dict(bound=index, state=state, cv_scopes=[d["scope"] for d in matching]))
    label, reason = "", "insufficient_affirmative_compatibility"
    if not jd["role"] or jd["role_precision"] != "occupation_rule" or not jd["role_evidence"]:
        reason = "unknown_generic_or_conflicting_occupation"
    elif jd["benchmark_scope"] == "outside_software_benchmark":
        reason = "outside_software_scope"
    elif any(v["state"] == "no" for v in outcomes + duration_states):
        label, reason = "0", "explicit_mandatory_contradiction"
    elif relation in {"same_role_assertion", "potentially_overlapping_functions"} and common:
        label, reason = "1", "affirmative_partial_technical_overlap"
        if (relation == "same_role_assertion" and outcomes and duration_states and
                all(v["state"] == "yes" for v in outcomes + duration_states) and
                not jd["unresolved_durations"] and not any(c["state"] == "unresolved" for c in jd["clauses"])):
            label, reason = "2", "all_observed_bounded_technical_conditions_supported"
    return dict(label_status="automatic_rule_proxy" if label else "insufficient_evidence", relevance_0_1_2=label,
                reason=reason, relation=relation, shared_skills=common, mandatory_states=outcomes, duration_states=duration_states)


LABEL_FIELDS = ("pair_id", "partition", "cv_id", "jd_id", "cv_version", "jd_version", "label_status", "relevance_0_1_2", "reason", "evidence_ref")


def preparation_facts(intake):
    records = read_lines(intake / "records.jsonl")
    cvs = {r["record_id"]: r for r in records if r["kind"] == "cv"}
    jobs = {r["record_id"]: r for r in records if r["kind"] == "jd"}
    require(all(r.get("metadata_version") == "catalogue-metadata-v4-title-taxonomy" and
                r.get("label_policy_status") == "requires_expanded_taxonomy_policy" for r in jobs.values()), "Wrong expanded taxonomy input")
    receipts = {r["job_id"]: r for r in read_json(intake / "catalogue/jd_extraction_evidence.json")}
    jd = {key: jd_facts(r, receipts[r["external_id"]]) for key, r in jobs.items()}
    authored = read_json(intake / "authored/evidence.json")
    if (intake / "prior/evidence.json").exists():
        authored += read_json(intake / "prior/evidence.json")
    by_id = {e["cv_id"]: e for e in authored}
    vocabulary = sorted({t for j in jd.values() for t in j["skills"]})
    cv = {key: cv_facts(r, by_id[r["external_id"]], vocabulary) for key, r in cvs.items()}
    return cvs, jobs, cv, jd


def expected_pairs(intake, jobs):
    _, train = csv_rows(intake / "train_candidates/pairs.csv")
    pairs = [(p["partition"], p["cv_id"], p["jd_id"]) for p in train]
    for a in read_lines(intake / "assignments.jsonl"):
        if a["kind"] == "cv" and a["partition"] in {"validation", "test"}:
            pairs.extend((a["partition"], a["record_id"], jid) for jid in sorted(jobs))
    require(len(pairs) == len(set(pairs)), "Duplicate candidate/census pair")
    return sorted(pairs)


def tally(rows, cvs, jobs):
    def counts(group):
        return dict(total=len(group), labels=dict(Counter(r["relevance_0_1_2"] or "unlabeled" for r in group)),
                    reasons=dict(Counter(r["reason"] for r in group)))
    by_partition = {p: counts([r for r in rows if r["partition"] == p]) for p in ("train", "validation", "test")}
    by_cv = {cid: dict(role=c["role"], **counts([r for r in rows if r["cv_id"] == cid])) for cid, c in cvs.items()}
    by_role = {role: counts([r for r in rows if cvs[r["cv_id"]]["role"] == role]) for role in sorted({c["role"] for c in cvs.values()})}
    jd_roles = {role or "unknown": counts([r for r in rows if jobs[r["jd_id"]]["role"] == role]) for role in sorted({j["role"] for j in jobs.values()})}
    complete = all(r["relevance_0_1_2"] != "" for r in rows)
    missing_train_classes = [label for label in ("0", "1", "2") if not by_partition["train"]["labels"].get(label)]
    return dict(version=VERSION, pair_count=len(rows), **counts(rows), partitions=by_partition, by_cv=by_cv,
                by_cv_role=by_role, by_jd_role=jd_roles, full_catalogue_judgments_complete=complete,
                full_catalogue_ranking_metrics_allowed=complete, ready_for_training=False, models_trained=0,
                final_test_ready=False, independent_gold=False,
                missing_train_classes=missing_train_classes,
                cv_without_label_2=sum(not v["labels"].get("2") for v in by_cv.values()),
                readiness_reason="Preparation only. Missing labels cannot be treated as zero; full-catalogue Recall/NDCG blocked when coverage is incomplete.")


def create_labels(intake, output):
    intake = Path(intake).resolve()
    checked = check_intake(intake)
    require(checked["structural_partition_ready"], "Intake partitions incomplete")
    input_hash = file_hash(intake / "manifest.json")
    protected = read_json(intake / "protected_input_hashes.json")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Protected inputs changed")
    cvs, jobs, cv, jd = preparation_facts(intake)
    folder = fresh_folder(output, (intake,))
    write_json(folder / "policy.json", POLICY)
    write_json(folder / "cv_facts.json", cv)
    write_json(folder / "jd_facts.json", jd)
    write_json(folder / "parsing_coverage.json", dict(jd_count=len(jd),
        jd_with_mandatory_technology=sum(any(c["state"] == "mandatory" for c in j["clauses"]) for j in jd.values()),
        jd_with_parsed_duration=sum(bool(j["durations"]) for j in jd.values()),
        jd_with_unresolved_duration=sum(bool(j["unresolved_durations"]) for j in jd.values()),
        clause_states=dict(Counter(c["state"] for j in jd.values() for c in j["clauses"])),
        cv_with_explicit_nonuse=sum(bool(c["nonuse"]) for c in cv.values()),
        interpretation="Small complete-clause grammar; coverage is not semantic accuracy"))
    rows, evidence = [], []
    for partition, cid, jid in expected_pairs(intake, jobs):
        pid = "PAIR_" + digest(cid + "|" + jid)[:32]
        decision = judge(cv[cid], jd[jid])
        rows.append(dict(pair_id=pid, partition=partition, cv_id=cid, jd_id=jid,
            cv_version=cvs[cid]["normalized_text_sha256"], jd_version=jobs[jid]["normalized_text_sha256"],
            **{k: decision[k] for k in ("label_status", "relevance_0_1_2", "reason")}, evidence_ref="evidence.jsonl#" + pid))
        evidence.append(dict(pair_id=pid, cv_fact=cid, jd_fact=jid, **decision))
    write_csv(folder / "labels.csv", rows, LABEL_FIELDS)
    write_lines(folder / "evidence.jsonl", evidence)
    summary = tally(rows, cvs, jobs)
    write_json(folder / "summary.json", summary)
    write_json(folder / "input_receipt.json", dict(intake_manifest_sha256=input_hash, policy_sha256=file_hash(folder / "policy.json"),
        input_artifacts=verify(intake, "authored-cv-intake")["artifacts"], lineage_and_exposure_preserved=True))
    shutil.copyfile(intake / "protected_input_hashes.json", folder / "protected_input_hashes.json")
    require(file_hash(intake / "manifest.json") == input_hash and all(file_hash(ROOT / p) == h for p, h in protected.items()), "Inputs changed")
    seal(folder, "expanded-proxy-labels", dict(policy_version=VERSION, intake_manifest_sha256=input_hash, models_trained=0))
    return {k: summary[k] for k in ("pair_count", "labels", "partitions", "ready_for_training", "final_test_ready")}


def check_labels(intake, artifact):
    intake, artifact = Path(intake), Path(artifact)
    verify(artifact, "expanded-proxy-labels")
    check_intake(intake)
    receipt = read_json(artifact / "input_receipt.json")
    require(receipt["intake_manifest_sha256"] == file_hash(intake / "manifest.json"), "Wrong intake parent")
    require(read_json(artifact / "policy.json") == POLICY, "Unsupported/changed frozen policy")
    require(receipt["policy_sha256"] == file_hash(artifact / "policy.json"), "Policy receipt mismatch")
    cvs, jobs, cv, jd = preparation_facts(intake)
    require(read_json(artifact / "cv_facts.json") == cv and read_json(artifact / "jd_facts.json") == jd, "Evidence facts differ from input")
    _, rows = csv_rows(artifact / "labels.csv")
    evidence = read_lines(artifact / "evidence.jsonl")
    expected = expected_pairs(intake, jobs)
    require(len(rows) == len(evidence) == len(expected), "Incomplete sampled/census grid")
    for row, ev, (part, cid, jid) in zip(rows, evidence, expected):
        pid = "PAIR_" + digest(cid + "|" + jid)[:32]
        decision = judge(cv[cid], jd[jid])
        require((row["partition"], row["cv_id"], row["jd_id"], row["pair_id"]) == (part, cid, jid, pid), "Pair partition/identity differs")
        require(all(row[k] == decision[k] for k in ("label_status", "relevance_0_1_2", "reason")), "Label does not reproduce frozen policy")
        require(ev == dict(pair_id=pid, cv_fact=cid, jd_fact=jid, **decision), "Evidence decision differs")
        require(row["cv_version"] == cvs[cid]["normalized_text_sha256"] and row["jd_version"] == jobs[jid]["normalized_text_sha256"] and
                row["evidence_ref"] == "evidence.jsonl#" + pid, "Text/evidence reference mismatch")
    require(read_json(artifact / "summary.json") == tally(rows, cvs, jobs), "Coverage report differs from actual labels")
    protected = read_json(artifact / "protected_input_hashes.json")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Protected originals changed")
    return dict(verified=True, pairs=len(rows), labels=dict(Counter(r["relevance_0_1_2"] or "unlabeled" for r in rows)),
                ready_for_training=False, final_test_ready=False)
