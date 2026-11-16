"""Versioned metadata overlay for a known-JD catalogue; never rewrites history."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil

from .catalogue import audit_evidence
from .common import (ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines,
                     require, seal, verify, write_csv, write_json, write_lines)
from .extraction import (MONTH_REQUIREMENT_PATTERN, SKILL_PATTERNS,
                         YEAR_REQUIREMENT_PATTERN, _clean_field, _span)
from .requirements_logic import requirement_logic

VERSION = "catalogue-metadata-v4-title-taxonomy"
# Occupation cues precede technologies. A tool/domain mention is not an occupation.
PRIORITY_ROLES = (
    ("CNC/CAM Manufacturing", r"\b(?:cnc|cad[\s-]*cam|mastercam)\b"),
    ("Industrial Automation", r"\bplc\b"),
    ("Education/Training", r"giáo\s+viên|giảng\s+viên|\b(?:lecturer|teacher)\b"),
    ("Sales/Business Development", r"phát\s+triển\s+kinh\s+doanh|\b(?:sales|business\s+development|presales?)\b"),
    ("Marketing", r"\bmarketing\b"),
    ("Material Development", r"\bmaterial\s+developer\b"),
)
SPECIFIC_ROLES = (
    ("Project Management", r"\b(?:project\s+manage(?:r|ment)|junior\s+pm)\b"),
    ("Product Management", r"\bproduct\s+(?:owner|manager)\b"),
    ("Scrum Master", r"\bscrum\s+master\b"),
    ("Business Analyst", r"\bbusiness\s+analyst\b|phân\s+tích\s+nghiệp\s+vụ"),
    ("Bridge Engineer", r"\b(?:bridge\s+(?:system|software)\s+engineer|brse)\b"),
    ("Engineering Management", r"\b(?:engineering\s+manager|software\s+development\s+manager|chief\s+technology\s+officer)\b|trưởng\s+phòng\s+công\s+nghệ"),
    ("IT Management", r"\bit\s+manager\b"),
    ("Technical Architecture", r"\b(?:solution|software|technical|database|data\s+solution)\s+architect\b"),
    ("Fullstack", r"\bfull[\s-]*(?:stack|stask)\b"),
    ("Desktop Application", r"\b(?:desktop|wpf|winforms)\b"),
    ("Database/SQL", r"\b(?:database\s+(?:administrator|engineer|developer)|dba|(?:sql|oracle)\s+developer)\b|quản\s+trị\s+csdl"),
    ("Data Governance", r"\bdata\s+governance\b"),
    ("Data Engineer", r"\b(?:data\s+integration\s+engineer|etl\s+developer)\b"),
    ("Data Scientist", r"\bdata\s+scientist\b"),
    ("AI/ML Engineer", r"\b(?:ai\s+(?:developer|solutions?\s+engineer|consultant)|text[\s-]to[\s-]speech\s+engineer)\b|kỹ\s+sư\s+ai\b"),
    ("Embedded Engineer", r"lập\s+trình\s+nhúng|\brtos\s+developer\b"),
    ("Network Engineering", r"\bnetwork\s+(?:solution\s+)?engineer\b|giải\s+pháp\s+mạng"),
    ("Security Engineer", r"an\s+toàn\s+thông\s+tin|\bnetwork\s+security\b"),
    ("Blockchain", r"\bblockchain\s+developer\b"),
    ("Backend Ruby", r"\bruby\s+on\s+rails\s+developer\b"),
    ("C/C++ Software", r"(?<!\w)c\s*/\s*c\+\+\s+developer|(?<!\w)c\+\+\s+developer"),
    ("COBOL Software", r"\bcobol\s+developer\b"),
    ("Game Design", r"\bgame\s+(?:experience\s+)?designer\b"),
    ("Technical Art", r"\btechnical\s+artist\b"),
    ("Mobile", r"\b(?:mobile\s+(?:app\s+developer|technical\s+lead)|flutter\s+dev)\b|lập\s+trình\s+android"),
    ("QA/Testing", r"\btesting\s+software\s+supervisor\b"),
)
BACKEND_CUE = re.compile(r"\bback[\s-]?end\b", re.I)
DEV_CUE = re.compile(r"\b(?:developer|engineer|dev|leader)\b|lập\s+trình|phát\s+triển\s+(?:phần\s+mềm|ứng\s+dụng)", re.I)
TITLE_STACKS = (
    ("Backend Node.js", r"\b(?:node[ .]?js|nestjs)\b"),
    ("Backend .NET", r"(?<!\w)(?:\.?net|c#|asp\.net)(?!\w)"),
    ("Backend PHP", r"\b(?:php|laravel)\b"),
    ("Backend Golang", r"\bgolang\b"),
)
EXTRA_SKILLS = {
    "nestjs": (r"\bnest\.?js\b", True), "node.js": (r"\bnode[ .]?js\b", True),
    "ruby": (r"\bruby\b", False), "rails": (r"\b(?:ruby\s+on\s+)?rails\b", True),
    "swift": (r"\bswift\b", False), "kotlin": (r"\bkotlin\b", False),
    "flutter": (r"\bflutter\b", True), "dart": (r"\bdart\b", False),
    "android": (r"\bandroid\b", True), "ios": (r"\bios\b", True),
    "unity": (r"\bunity\b", True), "unreal": (r"\bunreal\b", True),
    "pandas": (r"\bpandas\b", True), "numpy": (r"\bnumpy\b", True),
    "pytorch": (r"\bpytorch\b", True), "tensorflow": (r"\btensorflow\b", True),
    "spark": (r"\b(?:apache\s+)?spark\b", True), "airflow": (r"\b(?:apache\s+)?airflow\b", True),
    "dbt": (r"\bdbt\b", True), "etl": (r"\betl\b", False),
    "figma": (r"\bfigma\b", True), "sap": (r"\bsap\b", True),
    "abap": (r"\babap\b", False), "salesforce": (r"\bsalesforce\b", True),
    "wpf": (r"\bwpf\b", True), "cobol": (r"\bcobol\b", False),
    "rtos": (r"\brtos\b", True), "stm32": (r"\bstm32\b", True),
}
OUTSIDE = {r for r, _ in PRIORITY_ROLES}
GENERIC = {"Backend (unspecified stack)", "Software Developer (unspecified)"}
OPTIONAL = re.compile(r"ưu\s+tiên|không\s+bắt\s+buộc|không\s+(?:yêu\s+cầu|cần)|not\s+(?:required|necessary)|optional|preferred|nice\s+to", re.I)


def refine_role(row, previous):
    title = _clean_field(row, "title_for_matching")
    def collect(rules):
        return [(role, _span("title_for_matching", title, m, role=role, source=VERSION))
                for role, pattern in rules if (m := re.search(pattern, title, re.I))]
    hits = collect(PRIORITY_ROLES)
    if not hits:
        hits = collect(SPECIFIC_ROLES)
        # An explicit managerial/analyst/architecture occupation wins over its domain/tools.
        primary = [h for h in hits if h[0] in {"Project Management", "Product Management", "Business Analyst",
                   "Engineering Management", "IT Management", "Technical Architecture", "Education/Training"}]
        if primary:
            hits = primary
    if not hits and DEV_CUE.search(title) and (not previous["role"] or previous["role"].startswith("Backend ")):
        hits = collect(TITLE_STACKS)
        # Preserve previously detected competing explicit roles: Java + Node is not one role.
        previous_candidates = previous.get("role_candidates", [])
        if hits and any(r != hits[0][0] for r in previous_candidates):
            hits += [(r, ev) for r, ev in zip(previous_candidates, previous["role_evidence"])
                     if r not in {h[0] for h in hits}]
    if hits:
        roles = sorted({r for r, _ in hits})
        return (roles[0] if len(roles) == 1 else ""), [ev for _, ev in hits], roles
    if previous["role"] or previous.get("role_candidates"):
        return previous["role"], previous["role_evidence"], previous["role_candidates"]
    generic = BACKEND_CUE.search(title)
    if generic:
        role = "Backend (unspecified stack)"
        return role, [_span("title_for_matching", title, generic, role=role, source=VERSION)], [role]
    return "", previous["role_evidence"], previous["role_candidates"]


def refine_receipt(row, previous):
    receipt = deepcopy(previous)
    receipt["previous_extractor_version"] = previous["extractor_version"]
    receipt["extractor_version"] = VERSION
    receipt["role"], receipt["role_evidence"], receipt["role_candidates"] = refine_role(row, previous)
    for field in ("title_for_matching", "requirements_text", "tasks_text", "preferred_requirements_text"):
        text = _clean_field(row, field)
        for term, (pattern, is_stack) in EXTRA_SKILLS.items():
            for match in re.finditer(pattern, text, re.I):
                start = text.rfind("\n", 0, match.start()) + 1
                end = text.find("\n", match.end())
                sentence = text[start:end if end >= 0 else len(text)]
                optional = field == "preferred_requirements_text" or bool(OPTIONAL.search(sentence))
                span = _span(field, text, match, skill=term, section_type="optional_or_preferred" if optional else "core")
                if optional:
                    receipt["preferred_skill_evidence"].setdefault(term, span)
                else:
                    receipt["skill_evidence"].setdefault(term, span)
                    if is_stack:
                        receipt["stack_evidence"].setdefault(term, span)
    receipt["skills"] = sorted(receipt["skill_evidence"])
    receipt["stack"] = sorted(receipt["stack_evidence"])
    receipt["preferred_skills"] = sorted(receipt["preferred_skill_evidence"])
    receipt["requirement_clauses"] = requirement_logic(row, {**SKILL_PATTERNS, **EXTRA_SKILLS})
    receipt["unknown_fields"] = [f for f in ("role", "skills", "stack", "experience") if not receipt[f]]
    receipt["role_precision"] = ("unknown_or_conflicting" if not receipt["role"] else
                                 "generic" if receipt["role"] in GENERIC else "occupation_rule")
    receipt["benchmark_scope"] = "outside_software_benchmark" if receipt["role"] in OUTSIDE else "requires_protocol_mapping"
    receipt["experience_policy"] = "Preserved v3 explicit scopes/bounds; no months inferred from title, seniority or tools"
    return receipt


def missing_reasons(row, receipt):
    reasons = {}
    if not receipt["role"]:
        reasons["role"] = "conflicting_role_cues" if receipt["role_candidates"] else "no_supported_occupation_cue"
    if not receipt["skills"]:
        reasons["skills"] = "no_core_term_in_versioned_vocabulary"
    if not receipt["stack"]:
        reasons["stack"] = "no_core_stack_term_in_versioned_vocabulary"
    if not receipt["experience"]:
        reasons["experience"] = ("numeric_duration_without_supported_scope_or_minimum" if any(
            pattern.search(row.get("requirements_text", "")) for pattern in (YEAR_REQUIREMENT_PATTERN, MONTH_REQUIREMENT_PATTERN))
            else "no_numeric_duration_in_requirements")
    return reasons


def cv_plan(records):
    roles = Counter(r["role"] for r in records)
    # A first tranche, not a claim to cover every occupation in the corpus.
    selected = ("backend python", "backend java", "frontend", "devops/cloud", "qa/testing",
                "backend .net", "fullstack", "mobile", "data engineer", "ai/ml engineer")
    rows = [dict(role=role, jd_count=roles[role], jd_groups=len({r["group_id"] for r in records if r["role"] == role}),
                 proposed_cvs=20 if roles[role] else 0, reason="original target" if i < 5 else "broaden stack/domain coverage")
            for i, role in enumerate(selected)]
    count = sum(r["proposed_cvs"] for r in rows)
    return dict(status="design_only_no_cvs_generated", roles=rows, proposed_cv_count=count,
        uncovered_roles={r: n for r, n in sorted(roles.items()) if r not in selected},
        data_analyst="Still a research target; zero eligible JD previously observed. Resolve JD source before positive benchmark coverage.",
        families=dict(target=10, cvs_per_role_per_family=2, rule="Actual shared authoring frameworks; ancestry cannot be reset to obtain a split"),
        experience_kinds=["employment", "contract", "internship", "project", "unknown"],
        planned_cv_partitions=dict(train=count*6//10, validation=count*2//10, test=count*2//10),
        protocol="known-jd; shared full catalogue, new untouched CV source/template groups; preview until grouping checks",
        catalogue_jd_count=len(records), validation_pairs=count*2//10*len(records), test_pairs=count*2//10*len(records),
        training_sampling=dict(random_per_cv=10, hard_per_type=3, hard_types=["role", "stack", "experience"],
                               maximum_pairs=count*6//10*19, note="Upper bound before dedup/availability; candidates are not labels"),
        schema_required=["cv_id", "cv_text", "source_group", "template_group", "is_synthetic", "role", "skills", "stack",
                         "experience_json", "exposure", "text_scope", "lineage_json"],
        authoring_constraints=["No target JD, ranking, relevance label or copied JD sentences in authoring inputs",
            "Synthetic fictional identities only; literal skill and scoped-duration evidence in a sidecar",
            "Unknown duration remains {}; internship/project time is not professional time",
            "Same source/framework/near-duplicate family stays in one partition; record prior ancestors",
            "Old 60 CVs remain regression only; new CVs used for parser tuning become development",
            "One AI author is shared provenance, not independent real applicant evidence"],
        readiness_blockers=["Author and validate genuinely new source scenarios before splitting",
            "Expanded occupation taxonomy needs compatibility policy; different strings alone cannot imply label 0",
            "Unknown metadata must retain unlabeled status; no full-catalogue metrics from a silently filtered grid"])


def refine_catalogue(catalogue_run, output):
    source = Path(catalogue_run).resolve()
    verify(source, "jd-catalogue-expansion")
    source_hash = file_hash(source / "manifest.json")
    protected = read_json(source / "protected_input_hashes.json")
    require(all(file_hash(ROOT / p) == h for p, h in protected.items()), "Protected source/pilot changed")
    records = read_lines(source / "catalogue/records.jsonl")
    columns, raw_rows = csv_rows(source / "dataset/raw/000.csv")
    raw = {r["job_id"]: r for r in raw_rows}
    old_receipts = {r["job_id"]: r for r in read_json(source / "catalogue/metadata_evidence.json")}
    folder = fresh_folder(output, (source,))
    (folder / "snapshots").mkdir()
    shutil.copyfile(source / "dataset/raw/000.csv", folder / "snapshots/canonical_before.csv")
    shutil.copyfile(source / "catalogue/metadata_evidence.json", folder / "snapshots/evidence_before.json")
    for name in ("groups.json", "ids.json"):
        shutil.copyfile(source / "catalogue" / name, folder / name)
    receipts, updated, changes, canonical = [], [], [], []
    for original in records:
        row = raw[original["external_id"]]
        receipt = refine_receipt(row, old_receipts[row["job_id"]])
        receipts.append(receipt)
        new = deepcopy(original)
        new.update(role=receipt["role"].casefold(), skills=receipt["skills"], stack=receipt["stack"], experience=receipt["experience"],
                   metadata_version=VERSION, metadata_use_exposure="development", new_jd_holdout_eligible=False,
                   role_precision=receipt["role_precision"], benchmark_scope=receipt["benchmark_scope"],
                   label_policy_status="requires_expanded_taxonomy_policy")
        metadata_fields = {"role", "skills", "stack", "experience"}
        new["missing_fields"] = sorted(({f for f in original["missing_fields"] if f not in metadata_fields}) |
                                       {f for f in metadata_fields if not new[f]})
        # ID/text/lineage/group/quality/source exposure remain immutable; new exposure is an overlay.
        require(all(new[k] == original[k] for k in original if k not in metadata_fields | {"missing_fields"}), "Identity changed")
        require(new["experience"] == original["experience"], "Duration must not be inferred")
        updated.append(new)
        canonical.append(dict(row, extracted_role=receipt["role"], extracted_skills=";".join(receipt["skills"]),
                              extracted_stack=";".join(receipt["stack"]),
                              extracted_experience_json=json.dumps(receipt["experience"], ensure_ascii=False, sort_keys=True), extractor_version=VERSION))
        changes.append(dict(record_id=new["record_id"], job_id=row["job_id"],
            changed={f: dict(before=original[f], after=new[f]) for f in ("role", "skills", "stack", "experience") if original[f] != new[f]},
            missing_reasons=missing_reasons(row, receipt), role_precision=receipt["role_precision"], benchmark_scope=receipt["benchmark_scope"]))
    evidence_audit = audit_evidence(canonical, receipts)
    evidence_audit.update(extraction_rerun=True, duration_extraction_rerun=False)
    write_csv(folder / "canonical_jd_enriched.csv", canonical, columns)
    write_lines(folder / "records.jsonl", updated)
    write_json(folder / "jd_extraction_evidence.json", receipts)
    write_lines(folder / "metadata_changes.jsonl", changes)
    source_all = read_lines(source / "dataset/records.jsonl")
    group_ids = {r["group_id"] for r in updated}
    write_json(folder / "exposure_overlay.json", dict(reason="Catalogue used for parser/taxonomy development; known-JD only",
        group_ids=sorted(group_ids), record_ids=sorted(r["record_id"] for r in source_all if r["group_id"] in group_ids),
        historical_source_exposure_preserved=True, new_jd_holdout_eligible=False))
    plan = cv_plan(updated)
    write_json(folder / "cv_design_plan.json", plan)
    role_rows = [dict(role=role or "unknown", jd_count=n,
                     jd_groups=len({r["group_id"] for r in updated if r["role"] == role}))
                 for role, n in sorted(Counter(r["role"] for r in updated).items())]
    write_csv(folder / "role_coverage.csv", role_rows, ("role", "jd_count", "jd_groups"))
    summary = dict(version=VERSION, source_manifest_sha256=source_hash, jd_count=len(updated),
        groups=len(group_ids), changed_records=sum(bool(c["changed"]) for c in changes),
        fields_changed={f: sum(f in c["changed"] for c in changes) for f in ("role", "skills", "stack", "experience")},
        missing_before={f: sum(not r[f] for r in records) for f in ("role", "skills", "stack", "experience")},
        missing_after={f: sum(not r[f] for r in updated) for f in ("role", "skills", "stack", "experience")},
        role_precision=dict(Counter(r["role_precision"] for r in updated)),
        benchmark_scope=dict(Counter(r["benchmark_scope"] for r in updated)),
        missing_reasons=dict(Counter(v for c in changes for v in c["missing_reasons"].values())),
        evidence_audit=evidence_audit, source_csv_unchanged=3, pilot_files_unchanged=len(protected)-3,
        labels_created=0, models_trained=0, new_cvs_created=0, final_test_ready=False,
        limitation="Coverage, not accuracy. New taxonomy not compatible with role-string inequality as negative labels.")
    write_json(folder / "summary.json", summary)
    shutil.copyfile(source / "protected_input_hashes.json", folder / "protected_input_hashes.json")
    verify(source, "jd-catalogue-expansion")
    require(file_hash(source / "manifest.json") == source_hash and
            all(file_hash(ROOT / p) == h for p, h in protected.items()), "Input changed during refinement")
    seal(folder, "jd-metadata-refinement", dict(source_manifest_sha256=source_hash, extractor_version=VERSION))
    return summary
