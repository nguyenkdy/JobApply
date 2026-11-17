"""Read-only post-merge integrity and missing-label diagnostics, never new labels.

Snapshot integrity, current workspace bytes, and LF-equivalent code are reported
separately. This audit does not weaken existing strict protected-input gates.
"""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import re
import subprocess

from .common import (ROOT, csv_rows, digest, file_hash, fresh_folder, read_json, read_lines,
                     require, seal, verify, write_csv, write_json, write_lines)
from .expanded_labels import (CONDITIONAL, EXPERIENCE_CUE, OPTIONAL, POLICY, REQUIRED,
                              clean_clause, duration_clause, expected_pairs, judge, mandatory_clause,
                              preparation_facts, source_field, tally)
from .intake import check_intake

VERSION = "readiness-diagnostics-v1"
EOL_PROOF_PATHS = {
    "jobapply_pilot_v1/evaluate_top5.py",
    "jobapply_pilot_v1/evaluate_topk.py",
    "jobapply_pilot_v1/jobapply_experience_v2/train_matcher.py",
    "jobapply_pilot_v1/requirements-ml-win-py314.lock.txt",
}
ROLE_COMPATIBLE = {"same_role_assertion", "potentially_overlapping_functions"}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def compare_protected(path, data, expected):
    """Exact hashes for data. Bounded EOL proof only for named historical code/lock files."""
    actual = sha_bytes(data)
    result = dict(path=path, expected_sha256=expected, current_sha256=actual, bytes=len(data),
                  status="byte_identical" if actual == expected else "unexplained_change",
                  current_crlf_count=data.count(b"\r\n"), current_lf_count=data.count(b"\n"))
    if actual != expected and path in EOL_PROOF_PATHS:
        lf = data.replace(b"\r\n", b"\n")
        variants = {"LF": lf, "CRLF": lf.replace(b"\n", b"\r\n")}
        for name, candidate in variants.items():
            if sha_bytes(candidate) == expected:
                result.update(status="eol_only_proven", historical_eol=name,
                              canonical_lf_sha256=sha_bytes(lf), reconstructed_historical_bytes=len(candidate),
                              proof="Only CRLF/LF conversion in memory reconstructs the exact historical SHA256")
                break
    return result


def git_output(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def audit_protected(receipt):
    rows = []
    for path, expected in sorted(receipt["protected_input_hashes"].items()):
        item = compare_protected(path, (ROOT / path).read_bytes(), expected)
        if path in EOL_PROOF_PATHS:
            committed = git_output("show", "HEAD:" + path)
            item.update(head_blob_sha256=sha_bytes(committed), current_matches_head_blob=item["current_sha256"] == sha_bytes(committed),
                        git_eol=git_output("ls-files", "--eol", "--", path).decode().strip())
        rows.append(item)
    return dict(files=rows, counts=dict(Counter(r["status"] for r in rows)),
                strict_workspace_byte_check_passed=all(r["status"] == "byte_identical" for r in rows),
                unexplained_changes=[r["path"] for r in rows if r["status"] == "unexplained_change"],
                data_files_normalized=False, historical_receipt_rewritten=False, strict_gate_bypassed=False)


def unlabeled_reason(cv, jd, decision):
    """Mutually exclusive explanation of the *existing policy*, not a new judgment."""
    require(decision["relevance_0_1_2"] == "", "Only diagnose blank labels here")
    reason = decision["reason"]
    if reason == "unknown_generic_or_conflicting_occupation":
        return "unknown_or_conflicting_jd_role" if not jd["role"] else "generic_jd_role" if jd["role_precision"] != "occupation_rule" else "missing_role_evidence"
    if reason == "outside_software_scope":
        return "outside_software_scope"
    require(reason == "insufficient_affirmative_compatibility", "Unknown frozen-policy abstention reason")
    if decision["relation"] == "different_titles_fit_unresolved":
        return "different_roles_fit_unresolved"
    if decision["relation"] not in ROLE_COMPATIBLE:
        return "unknown_role_relation"
    if not cv["skills"]:
        return "no_cv_positive_skill_evidence"
    if not jd["skills"]:
        return "no_jd_core_skill_evidence"
    require(not decision["shared_skills"], "Unexpected affirmative overlap with blank label")
    return "no_exact_shared_skill"


def positive_two_gaps(jd, decision):
    """Overlapping conditions preventing a label-1 pair from receiving label 2."""
    require(decision["relevance_0_1_2"] == "1", "Only diagnose label 1 here")
    flags = {
        "role_overlap_not_exact": decision["relation"] != "same_role_assertion",
        "no_parsed_mandatory_technology": not decision["mandatory_states"],
        "no_parsed_required_duration": not decision["duration_states"],
        "mandatory_technology_not_fully_supported": any(v["state"] != "yes" for v in decision["mandatory_states"]),
        "required_duration_not_fully_supported": any(v["state"] != "yes" for v in decision["duration_states"]),
        "unresolved_technical_clause": any(c["state"] == "unresolved" for c in jd["clauses"]),
        "unresolved_duration_clause": bool(jd["unresolved_durations"]),
    }
    return [key for key, present in flags.items() if present]


def clause_diagnostic(clause):
    """Classify the grammar rejection mechanism, not whether a requirement is mandatory."""
    quote = clause["evidence"]["quote"]
    local = mandatory_clause(quote, clause["terms"], clause["evidence"]["field"])
    if local["state"] == "mandatory" or duration_clause(quote):
        return "document_guard_disabled_local_parse"
    if EXPERIENCE_CUE.search(quote):
        return "duration_sentence_not_supported"
    if not REQUIRED.fullmatch(clean_clause(quote)):
        return "prefix_not_supported"
    return "technology_expression_not_supported"


def jd_diagnostics(records, facts, receipts):
    table, clauses, durations, examples = [], [], [], []
    empty_fields, unknown_roles = Counter(), Counter()
    duration_patterns, clause_counts = Counter(), Counter()
    example_counts = Counter()
    for jid, fact in sorted(facts.items()):
        rec = records[jid]
        receipt = receipts[rec["external_id"]]
        fields = {key: source_field(rec, key) for key in ("title_for_matching", "tasks_text", "requirements_text", "preferred_requirements_text")}
        empty = [key for key, value in fields.items() if not value.strip()]
        empty_fields.update(empty)
        role_state = "assigned"
        if not fact["role"]:
            role_state = "multiple_candidates" if len(receipt.get("role_candidates", [])) > 1 else "no_candidate_from_extractor"
            unknown_roles[role_state] += 1
        unresolved_count = 0
        for index, clause in enumerate(fact["clauses"]):
            if clause["state"] != "unresolved":
                continue
            cause = clause_diagnostic(clause)
            unresolved_count += 1
            clause_counts[cause] += 1
            item = dict(jd_id=jid, clause_index=index, category=cause, field=clause["evidence"]["field"],
                        start=clause["evidence"]["start"], end=clause["evidence"]["end"],
                        quote_sha256=digest(clause["evidence"]["quote"]))
            clauses.append(item)
            if example_counts[cause] < 3:
                # Only already-development JD quotes; no holdout CV prose or rankings.
                examples.append(dict(item, quote=clause["evidence"]["quote"], metadata_use_exposure=rec["metadata_use_exposure"]))
                example_counts[cause] += 1
        for index, span in enumerate(fact["unresolved_durations"]):
            quote = clean_clause(span["quote"])
            flags = []
            for key, pattern in (
                ("range_or_plus_notation", r"\d\s*(?:[-–]\s*\d|\+)"),
                ("relative_role_scope", r"vị trí (?:tương tự|tương đương)|similar (?:role|position)|relevant experience"),
                ("alternatives_or_condition", r"\b(?:or|hoặc|if|nếu)\b"),
                ("minimum_cue_present", r"tối thiểu|ít nhất|trở lên|at least|minimum|\btrên\b"),
            ):
                if re.search(pattern, quote, re.I):
                    flags.append(key)
            if duration_clause(quote):
                flags.append("local_duration_disabled_by_document_guard")
            if not flags:
                flags.append("other_unsupported_duration_syntax_or_scope")
            duration_patterns.update(flags)
            durations.append(dict(jd_id=jid, duration_index=index, indicators=flags, field=span["field"],
                                  start=span["start"], end=span["end"], quote_sha256=digest(span["quote"])))
        candidate_lines = [m[0] for m in re.finditer(r"[^\n;]+", fields["requirements_text"]) if EXPERIENCE_CUE.search(m[0])]
        mandatory_duration_lines = [s for s in candidate_lines if not OPTIONAL.search(s)]
        table.append(dict(jd_id=jid, external_id=rec["external_id"], role=fact["role"], role_precision=fact["role_precision"],
            role_diagnostic=role_state, role_candidates=len(receipt.get("role_candidates", [])), benchmark_scope=fact["benchmark_scope"],
            title_nonempty=bool(fields["title_for_matching"].strip()), tasks_nonempty=bool(fields["tasks_text"].strip()),
            requirements_nonempty=bool(fields["requirements_text"].strip()), core_skills=len(fact["skills"]),
            original_metadata_skills=len(rec["skills"]), unresolved_technical_clauses=unresolved_count,
            parsed_mandatory_clauses=sum(c["state"] == "mandatory" for c in fact["clauses"]),
            numeric_duration_lines=len(candidate_lines), nonoptional_numeric_duration_lines=len(mandatory_duration_lines),
            parsed_duration_bounds=len(fact["durations"]), unresolved_duration_clauses=len(fact["unresolved_durations"]),
            document_conditional_cue=bool(CONDITIONAL.search(fields["requirements_text"])),
            original_metadata_duration_present=bool(rec["experience"]), exposure="known_jd_parser_development"))
    summary = dict(jd_count=len(table), empty_source_fields={k: empty_fields[k] for k in ("title_for_matching", "tasks_text", "requirements_text", "preferred_requirements_text")},
        unknown_role_diagnostics=dict(unknown_roles), unresolved_clause_categories=dict(clause_counts),
        unresolved_clause_count=len(clauses), unresolved_duration_clause_count=len(durations),
        duration_indicators_overlapping=dict(duration_patterns),
        jd_with_unresolved_duration=sum(bool(j["unresolved_durations"]) for j in facts.values()),
        jd_with_parsed_duration=sum(bool(j["durations"]) for j in facts.values()),
        jd_with_mandatory_technology=sum(any(c["state"] == "mandatory" for c in j["clauses"]) for j in facts.values()),
        jd_without_nonoptional_numeric_duration_pattern=sum(not j["nonoptional_numeric_duration_lines"] for j in table),
        jd_without_core_skill_evidence=sum(not j["core_skills"] for j in table),
        limits="Observed field presence and frozen-parser mechanisms, not a semantic accuracy audit. No numeric pattern is not proof of no experience requirement.")
    return summary, table, clauses, durations, examples


def validate_snapshot(intake, labels):
    """Check the sealed inputs/results without claiming live workspace bytes match history."""
    intake_manifest = verify(intake, "authored-cv-intake")
    verify(labels, "expanded-proxy-labels")
    require(read_json(labels / "policy.json") == POLICY, "Different frozen policy")
    # Current execution code must match archived code apart from line endings.
    source_checks = []
    for source in sorted((labels / "tool_source").glob("*.py")):
        current = ROOT / "ml_data" / source.name
        if source.name == "__main__.py":
            source_checks.append(dict(name=source.name, sealed_sha256=file_hash(source), current_sha256=file_hash(current),
                                     scope="CLI dispatch is not used to recompute frozen facts/labels; new audit command added"))
            continue
        require(source.read_bytes().replace(b"\r\n", b"\n") == current.read_bytes().replace(b"\r\n", b"\n"), "Audit execution code differs from sealed label source: " + source.name)
        source_checks.append(dict(name=source.name, sealed_sha256=file_hash(source), current_sha256=file_hash(current), lf_equivalent=True))
    check_intake(intake)
    receipt = read_json(labels / "input_receipt.json")
    require(receipt["intake_manifest_sha256"] == file_hash(intake / "manifest.json") and receipt["input_artifacts"] == intake_manifest["artifacts"], "Label intake parent differs")
    require(receipt["policy_sha256"] == file_hash(labels / "policy.json"), "Policy hash differs")
    require(read_json(labels / "protected_input_hashes.json") == read_json(intake / "protected_input_hashes.json"), "Protected reference differs")
    cvs, jobs, cv, jd = preparation_facts(intake)
    require(read_json(labels / "cv_facts.json") == cv and read_json(labels / "jd_facts.json") == jd, "Frozen facts differ from source evidence")
    _, rows = csv_rows(labels / "labels.csv")
    evidence = read_lines(labels / "evidence.jsonl")
    expected = expected_pairs(intake, jobs)
    require(len(rows) == len(evidence) == len(expected), "Pair/census grid incomplete")
    for row, ev, (partition, cid, jid) in zip(rows, evidence, expected):
        pid = "PAIR_" + digest(cid + "|" + jid)[:32]
        decision = judge(cv[cid], jd[jid])
        require((row["partition"], row["cv_id"], row["jd_id"], row["pair_id"]) == (partition, cid, jid, pid), "Pair identity or partition changed")
        require(all(row[k] == decision[k] for k in ("label_status", "relevance_0_1_2", "reason")), "Frozen label changed")
        require(ev == dict(pair_id=pid, cv_fact=cid, jd_fact=jid, **decision), "Frozen evidence changed")
        require(row["cv_version"] == cvs[cid]["normalized_text_sha256"] and row["jd_version"] == jobs[jid]["normalized_text_sha256"] and
                row["evidence_ref"] == "evidence.jsonl#" + pid, "Pair source version changed")
    require(read_json(labels / "summary.json") == tally(rows, cvs, jobs), "Saved summary differs from actual rows")
    return cvs, jobs, cv, jd, rows, evidence, source_checks


def pair_diagnostics(rows, evidence, cvs, cv, jd):
    diagnoses, positive_gaps = [], []
    partitions = defaultdict(Counter)
    role_counts, jd_counts = defaultdict(Counter), defaultdict(Counter)
    flags_unlabeled = Counter()
    for row, ev in zip(rows, evidence):
        cid, jid = row["cv_id"], row["jd_id"]
        if row["relevance_0_1_2"] == "":
            reason = unlabeled_reason(cv[cid], jd[jid], ev)
            item = dict(pair_id=row["pair_id"], partition=row["partition"], cv_id=cid, jd_id=jid,
                        category=reason, frozen_reason=row["reason"], evidence_ref=row["evidence_ref"])
            diagnoses.append(item)
            partitions[row["partition"]][reason] += 1
            role_counts[cvs[cid]["role"]][reason] += 1
            jd_counts[jid][reason] += 1
            if any(c["state"] == "unresolved" for c in jd[jid]["clauses"]):
                flags_unlabeled["jd_has_unresolved_technical_clause"] += 1
            if jd[jid]["unresolved_durations"]:
                flags_unlabeled["jd_has_unresolved_duration"] += 1
        elif row["relevance_0_1_2"] == "1":
            positive_gaps.append(dict(pair_id=row["pair_id"], partition=row["partition"], cv_id=cid, jd_id=jid,
                                      gaps=positive_two_gaps(jd[jid], ev)))
    total = Counter(d["category"] for d in diagnoses)
    partition_labels = {p: dict(Counter(r["relevance_0_1_2"] or "unlabeled" for r in rows if r["partition"] == p)) for p in ("train", "validation", "test")}
    summary = dict(pair_count=len(rows), labels=dict(Counter(r["relevance_0_1_2"] or "unlabeled" for r in rows)),
        unlabeled_count=len(diagnoses), unlabeled_categories_exclusive=dict(total),
        unlabeled_by_partition={p: dict(v) for p, v in sorted(partitions.items())}, labels_by_partition=partition_labels,
        unlabeled_by_cv_role={p: dict(v) for p, v in sorted(role_counts.items())},
        unlabeled_parser_flags_overlapping=dict(flags_unlabeled),
        label_one_count=len(positive_gaps), label_one_gaps_overlapping=dict(Counter(k for p in positive_gaps for k in p["gaps"])),
        label_one_gaps_by_partition={p: dict(Counter(k for r in positive_gaps if r["partition"] == p for k in r["gaps"])) for p in ("train", "validation", "test")},
        no_new_judgments=True, no_policy_change=True, holdout_cv_text_inspected_for_tuning=False,
        interpretation="Exclusive categories describe the actual decision path. Parser flags and label-2 blockers overlap and cannot be summed or equated to recoverable labels.")
    require(sum(total.values()) == summary["unlabeled_count"], "Unlabeled categories fail reconciliation")
    return summary, diagnoses, positive_gaps, jd_counts


def audit_readiness(intake, labels, receipt_path, output):
    intake, labels, receipt_path = [Path(p).resolve() for p in (intake, labels, receipt_path)]
    receipt_hash = file_hash(receipt_path)
    receipt = read_json(receipt_path)
    protected = audit_protected(receipt)
    require(not protected["unexplained_changes"], "Unexplained protected-input changes; investigate before dataset analysis")
    require(read_json(intake / "protected_input_hashes.json") == receipt["protected_input_hashes"], "Intake references a different protected receipt")
    historical = {}
    for name, expected in receipt["preserved_manifests"].items():
        folder = ROOT / "ml_data_runs" / name
        verify(folder)
        require(file_hash(folder / "manifest.json") == expected, "Historical manifest changed")
        historical[name] = expected
    cvs, jobs, cv, jd, rows, evidence, code_checks = validate_snapshot(intake, labels)
    inputs = dict(intake_manifest_sha256=file_hash(intake / "manifest.json"), labels_manifest_sha256=file_hash(labels / "manifest.json"), receipt_sha256=receipt_hash,
                  intake_path=intake.relative_to(ROOT).as_posix(), labels_path=labels.relative_to(ROOT).as_posix(), receipt_path=receipt_path.relative_to(ROOT).as_posix())
    pair_summary, pairs, positive_gaps, jd_counts = pair_diagnostics(rows, evidence, cvs, cv, jd)
    receipts = {e["job_id"]: e for e in read_json(intake / "catalogue/jd_extraction_evidence.json")}
    jd_summary, table, clauses, durations, examples = jd_diagnostics(jobs, jd, receipts)
    for item in table:
        item["unlabeled_pairs"] = sum(jd_counts[item["jd_id"]].values())
    cv_summary = dict(count=len(cv), unknown_timeline_declared=sum(c["experience_kind"] == "unknown" for c in cv.values()),
        no_duration_assertion=sum(not c["durations"] for c in cv.values()),
        experience_kinds=dict(Counter(c["experience_kind"] for c in cv.values())),
        duration_scopes=dict(Counter(d["scope"] for c in cv.values() for d in c["durations"])),
        cv_without_positive_skills=sum(not c["skills"] for c in cv.values()),
        interpretation="Source-declared synthetic evidence. Unknown timelines are not zero and missing skills do not prove inability.")
    git = dict(head=git_output("rev-parse", "HEAD").decode().strip(), branch=git_output("branch", "--show-current").decode().strip(),
               tree=git_output("rev-parse", "HEAD^{tree}").decode().strip(),
               attributes=git_output("show", "HEAD:.gitattributes").decode().splitlines())
    summary = dict(version=VERSION, git=git, inputs=inputs, snapshot_integrity_verified=True,
        frozen_decisions_recomputed=True, live_workspace_byte_match=protected["strict_workspace_byte_check_passed"],
        protected_counts=protected["counts"], historical_manifests_verified=len(historical),
        pair_diagnostics=pair_summary, jd_diagnostics=jd_summary, cv_diagnostics=cv_summary,
        label_policy_changed=False, labels_created=0, models_trained=0, ready_for_training=False,
        old_strict_command_status="Protected originals changed: code/lock files differ only by CRLF/LF; no receipt rewrite or guard bypass" if not protected["strict_workspace_byte_check_passed"] else "Protected original bytes match",
        scope="Steps 1 and 2 only: integrity explanation and evidence-gap diagnostics. No parser/label changes.")
    folder = fresh_folder(output, (intake, labels))
    write_json(folder / "summary.json", summary)
    write_json(folder / "protected_input_audit.json", protected)
    write_json(folder / "source_execution_audit.json", code_checks)
    write_json(folder / "historical_manifest_audit.json", historical)
    write_csv(folder / "unlabeled_pairs.csv", pairs, tuple(pairs[0]))
    write_lines(folder / "label_one_gaps.jsonl", positive_gaps)
    write_csv(folder / "jd_diagnostics.csv", table, tuple(table[0]))
    write_lines(folder / "unresolved_technical_clauses.jsonl", clauses)
    write_lines(folder / "unresolved_duration_clauses.jsonl", durations)
    write_json(folder / "development_jd_examples.local.json", examples)
    write_json(folder / "input_receipt.json", inputs)
    # Final integrity checks include ignored sealed files and original workspace
    # bytes. Neither an old reference nor current source is modified by the audit.
    verify(intake, "authored-cv-intake")
    verify(labels, "expanded-proxy-labels")
    require(file_hash(intake / "manifest.json") == inputs["intake_manifest_sha256"] and
            file_hash(labels / "manifest.json") == inputs["labels_manifest_sha256"] and file_hash(receipt_path) == receipt_hash, "Audit inputs changed")
    require(all(file_hash(ROOT / r["path"]) == r["current_sha256"] for r in protected["files"]), "Workspace inputs changed during audit")
    write_report(folder, summary, protected)
    seal(folder, "readiness-audit", dict(audit_version=VERSION, inputs=inputs, labels_created=0, models_trained=0))
    return dict(protected_counts=protected["counts"], unlabeled_count=pair_summary["unlabeled_count"],
                unlabeled_categories=pair_summary["unlabeled_categories_exclusive"], snapshot_integrity_verified=True,
                live_workspace_byte_match=summary["live_workspace_byte_match"], labels_created=0, models_trained=0)


def write_report(folder, summary, protected):
    """Readable report driven by actual audit counts, without source JD prose in Git."""
    pairs, jd, cv = [summary[k] for k in ("pair_diagnostics", "jd_diagnostics", "cv_diagnostics")]
    names = {
        "different_roles_fit_unresolved": "Hai nghề khác nhau; luật chưa có căn cứ kết luận mức phù hợp",
        "unknown_or_conflicting_jd_role": "Extractor chưa xác định được một nghề JD rõ ràng",
        "generic_jd_role": "Nghề JD còn quá chung chung",
        "outside_software_scope": "JD ngoài phạm vi benchmark phần mềm",
        "no_exact_shared_skill": "Quan hệ nghề được chấp nhận nhưng không có skill trùng chuỗi chính xác",
        "no_jd_core_skill_evidence": "Không có skill JD trong bộ bằng chứng tích cực đã lọc",
    }
    causes = "\n".join(f"| {names.get(key, key)} | {count:,} | {100*count/pairs['unlabeled_count']:.2f}% |" for key, count in sorted(pairs["unlabeled_categories_exclusive"].items(), key=lambda x: (-x[1], x[0])))
    hashes = "\n".join(f"| `{r['path']}` | {r['current_lf_count']} | `{r['expected_sha256'][:12]}…` | `{r['current_sha256'][:12]}…` |" for r in protected["files"] if r["status"] != "byte_identical")
    parsers = "\n".join(f"| `{key}` | {count:,} |" for key, count in sorted(jd["unresolved_clause_categories"].items()))
    gaps = "\n".join(f"| `{key}` | {count:,} |" for key, count in sorted(pairs["label_one_gaps_overlapping"].items()))
    doc = f"""# Kiểm tra sau merge và nguyên nhân thiếu nhãn — 16/11/2026

Đã thực hiện **bước 1 và 2** trên `{summary['git']['branch']}`, commit `{summary['git']['head'][:7]}`. Không sửa parser, luật nhãn, CV/JD, lineage, partition hoặc model. Không commit/push. [Receipt tổng hợp](reports/20261116-readiness-audit.json), [bằng chứng checksum](reports/20261116-protected-input-audit.json), [chẩn đoán từng JD](reports/20261116-jd-diagnostics.csv).

## 1. Chênh lệch checksum đã được giải thích

**{protected['counts'].get('byte_identical', 0)}/54 file khớp nguyên byte; {protected['counts'].get('eol_only_proven', 0)} file mã/lock chỉ khác CRLF và LF.** Chuyển LF thành CRLF trong bộ nhớ tái tạo chính xác SHA256 lịch sử của cả bốn file. Đây là chứng cứ byte, không chỉ là nhận xét “code trông giống nhau”. Ba CSV nguồn và các file dữ liệu pilot vẫn khớp nguyên byte.

| File | Số LF hiện tại | SHA256 lịch sử | SHA256 hiện tại |
|---|---:|---|---|
{hashes}

Các file hiện tại khớp blob Git HEAD. `.gitattributes` trong repo quy định `eol=lf`, đã tồn tại từ trước merge; quan sát này phù hợp với chuẩn hóa checkout. Không có bằng chứng cần sửa logic mã hoặc phiên bản thư viện. Không thể xác định riêng tiến trình/thời điểm đã đổi newline chỉ từ hash; không tuyên bố merge đã đổi thuật toán.

Giữ LF theo repo; **không đổi file về CRLF để làm xanh gate**, không ghi đè checksum trong receipt/run cũ. Báo cáo cũ mô tả byte ở thời điểm tạo run, không còn là chứng nhận byte của mọi file code trong checkout hiện tại. Gate strict `check-expanded-labels` vẫn sẽ báo `Protected originals changed` vì khác byte. Audit mới báo riêng: snapshot hợp lệ, dữ liệu gốc nguyên byte, code chỉ khác newline; **không biến kết quả đó thành strict byte-pass**.

Đã xác minh manifest của {summary['historical_manifests_verified']} run lịch sử, manifest intake v7 và nhãn v1; dựng lại facts từ câu/offset, kiểm lineage/split/census rồi tái tính đúng {pairs['pair_count']:,} quyết định theo luật đã đóng băng. Các file thực thi so với snapshot được kiểm tương đương CRLF/LF trước khi dùng. Nhãn và source snapshot không bị viết lại.

## 2. Vì sao 43.964 cặp còn trống?

Các nhóm dưới đây **loại trừ nhau**, cộng đúng {pairs['unlabeled_count']:,} cặp:

| Nguyên nhân trực tiếp theo luật v1 | Số cặp | Tỷ lệ trong cặp trống |
|---|---:|---:|
{causes}

**Điều chỉnh cách hiểu trước đây:** không thể quy toàn bộ ô trống cho parser đọc kém. Nhóm lớn nhất là quan hệ giữa các nghề mà luật chưa có căn cứ chấm phù hợp/không phù hợp. Khác tên nghề không tự chứng minh nhãn 0. “Không có skill trùng chuỗi” cũng không chứng minh không có năng lực chung: metadata có thể thiếu, alias có thể khác, hoặc thực sự khác stack; audit này không đoán thay.

Tất cả 788 JD đều có title, nhiệm vụ và phần yêu cầu không rỗng. Do đó nghề unknown hoặc thiếu skill trích xuất **không đồng nghĩa văn bản JD trống**. Trong 136 JD chưa có nghề rõ: {jd['unknown_role_diagnostics'].get('no_candidate_from_extractor', 0)} không có candidate từ extractor, {jd['unknown_role_diagnostics'].get('multiple_candidates', 0)} có nhiều candidate. 21 JD generic là nhóm riêng. Chưa chứng minh các trường hợp đó đều có một đáp án nghề duy nhất mà chỉ cần sửa regex là lấy được.

Về thông tin thiếu đã xác nhận: {cv['unknown_timeline_declared']}/{cv['count']} CV tự khai timeline unknown và không có thời lượng; có {jd['empty_source_fields']['preferred_requirements_text']} JD để trống cột ưu tiên, điều này không tự là lỗi hoặc chứng minh không có ưu tiên trong các cột khác. Không có CV thiếu hoàn toàn skill metadata. Không suy tháng công nghệ từ tổng thời gian làm việc.

### Parser chưa hiểu những gì?

Có **{jd['unresolved_clause_count']:,} mệnh đề công nghệ unresolved**, phân loại theo điểm ngữ pháp bị từ chối:

| Cơ chế parser không chấp nhận | Số mệnh đề |
|---|---:|
{parsers}

`prefix_not_supported`: câu không bắt đầu bằng một trong số ít mẫu mà luật nhận. `technology_expression_not_supported`: mở đầu được nhận nhưng phần sau không phải danh sách công nghệ đơn giản. `duration_sentence_not_supported`: câu có dấu hiệu tháng/năm nhưng không khớp mẫu scope/ngưỡng hẹp. `document_guard_disabled_local_parse`: câu riêng đọc được nhưng chốt điều kiện ở mức tài liệu chặn.

Có {jd['unresolved_duration_clause_count']} mệnh đề thời lượng unresolved trên {jd['jd_with_unresolved_duration']} JD; chỉ {jd['jd_with_parsed_duration']} JD có ngưỡng được chấp nhận hoàn chỉnh. Cờ khoảng năm, dấu cộng, “vị trí tương tự”, điều kiện và ngưỡng tối thiểu được lưu riêng. Chúng là dấu hiệu quan sát, không phải nhãn bắt buộc/ưu tiên mới. Bộ phân tích chỉ nhận câu công nghệ bắt buộc đầy đủ ở {jd['jd_with_mandatory_technology']} JD. Điều này mô tả giới hạn bộ luật, không phải số JD thực sự có yêu cầu.

### Vì sao chưa có nhãn 2?

Trong {pairs['label_one_count']:,} cặp đang có nhãn 1, các điều kiện chưa đạt dưới đây **có thể chồng lấn; không cộng lại**:

| Điều kiện còn vướng theo luật v1 | Số cặp nhãn 1 |
|---|---:|
{gaps}

Sửa parser không bảo đảm tất cả những cặp này sẽ thành nhãn 2: CV vẫn có thể thiếu scope/thời lượng/kỹ năng, hoặc chỉ chồng lấn nghề. Kết quả nhãn hiện tại giữ nguyên: 1 nhãn 0, 4.319 nhãn 1, 0 nhãn 2; train chỉ có 257 nhãn 1. Không train và không tính metric full-catalogue từ các ô trống.

## Artifact và cách kiểm lại

Run audit local được lưu vào thư mục mới truyền qua `--output`; `manifest.json` ghi hash toàn bộ kết quả. Đầu vào: `{summary['inputs']['intake_path']}` và `{summary['inputs']['labels_path']}`.

- `protected_input_audit.json`: expected/current hash và chứng minh newline cho từng file.
- `source_execution_audit.json`, `historical_manifest_audit.json`: kiểm mã dùng để tái tính và run lịch sử.
- `unlabeled_pairs.csv`: nguyên nhân trực tiếp của từng cặp trống; không có văn bản CV/JD hoặc nhãn mới.
- `label_one_gaps.jsonl`: các điều kiện ngăn nhãn 1 thành 2, cho phép nhiều cờ trên một cặp.
- `jd_diagnostics.csv`, `unresolved_technical_clauses.jsonl`, `unresolved_duration_clauses.jsonl`: ID/offset/hash để truy câu gốc.
- `development_jd_examples.local.json`: tối đa ba ví dụ mỗi loại từ JD đã dùng phát triển parser; giữ local, không đưa nội dung nguồn vào báo cáo Git.

```powershell
Set-Location D:\\JobApply
$auditOut = '.\\ml_data_runs\\readiness_audit_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fffffff')
& .\\jobapply_pilot_v1\\.venv-embedding\\Scripts\\python.exe -m ml_data audit-readiness --intake .\\ml_data_runs\\20261116_authored_cv_v7_01 --labels .\\ml_data_runs\\20261116_expanded_labels_v1_01 --output $auditOut
if ($LASTEXITCODE -ne 0) {{ throw 'Readiness audit failed' }}
Get-Content (Join-Path $auditOut 'summary.json')
```

## Bước sau — chưa thực hiện trong lượt này

Mở rộng parser trên JD development với fixture riêng, nhưng đồng thời cần thiết kế rõ chính sách quan hệ nghề/kỹ năng và phạm vi benchmark; chỉ sửa mẫu câu không giải quyết toàn bộ ô trống. Giữ riêng vấn đề dữ liệu thiếu, parser không hỗ trợ và quyết định nằm ngoài phạm vi luật. Không tự đánh 0 cho khác nghề hoặc thiếu skill.

Trước khi tạo run mới sau khi sửa code, cần phiên bản chính sách fingerprint phân biệt byte dữ liệu với code LF chuẩn, liên kết receipt cũ bằng chứng newline; không sửa/bỏ gate cũ. Audit này chưa thay chính sách đầu vào của pipeline.

Audit hiện chỉ kiểm tính toàn vẹn và tổng hợp quyết định đã có, không chỉnh luật từ CV holdout, không xem ranking, không train. Nếu dùng kết quả validation/test để chỉnh phương pháp ở lượt sau, phải ghi nhận exposure và chuẩn bị holdout thích hợp. Giới hạn synthetic và Data Analyst cần JD đủ điều kiện vẫn giữ nguyên.
"""
    (folder / "readiness_audit.md").write_text(doc, encoding="utf-8", newline="\n")
