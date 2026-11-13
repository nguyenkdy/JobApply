"""Audit supplied upstream stages and prepare a conservative, unlabeled JD import."""
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
import shutil

from .common import (ROOT, csv_rows, digest, file_hash, fresh_folder, normalize,
                     read_lines, require, seal, write_csv, write_json, write_lines)
from .grouping import group_records, near_pairs
from .ingest import ingest, pilot_anchors, record

VERSION = "upstream-observation-v1"
FILES = ("job_descriptions.csv", "jobs_clean.csv", "jobs_matching.csv")
PROFESSIONAL = ("title_for_matching", "tasks_text", "requirements_text", "preferred_requirements_text",
                "unclassified_professional_text", "match_text")
ERROR_CELL = re.compile(r"#(?:NAME\?|REF!|VALUE!|DIV/0!|N/A|NUM!|NULL!)", re.I)
ROLES = ("Backend Python", "Backend Java", "Frontend", "DevOps", "QA/Testing", "Data Analyst")


def lossless_hash(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()


def read_stage(path):
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
        encoding = "UTF-8 BOM" if data.startswith(b"\xef\xbb\xbf") else "UTF-8"
    except UnicodeDecodeError:
        text = data.decode("utf-8-sig", errors="surrogateescape")
        encoding = "not valid UTF-8; lossless surrogateescape for CSV structure only; encoding/original text unresolved"
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    rows = list(reader)
    fields = reader.fieldnames or []
    require(fields and len(fields) == len(set(fields)), "Empty/duplicate CSV schema")
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), "Malformed CSV records")
    bad = [i for i, row in enumerate(rows, 1) if any(0xdc80 <= ord(c) <= 0xdcff for v in row.values() for c in v)]
    replacement = [i for i, row in enumerate(rows, 1) if any("\ufffd" in v for v in row.values())]
    text_field = "match_text" if "match_text" in fields else "description"
    exact = Counter(lossless_hash(row[text_field]) for row in rows)
    normalized = Counter(lossless_hash(normalize(row[text_field]).casefold()) for row in rows)
    representatives = {}
    for i, row in enumerate(rows, 1):
        value = normalize(row[text_field])
        representatives.setdefault(lossless_hash(value.casefold()), dict(record_id=str(i), text_normalized=value))
    near = [dict(left_row=int(a), right_row=int(b), jaccard=score) for a, b, score in near_pairs(list(representatives.values()), 0.85)]
    ids = Counter(r["job_id"] for r in rows) if "job_id" in fields else None
    profile = dict(file=path.name, bytes=len(data), sha256=file_hash(path), encoding=encoding, fields=fields, records=len(rows),
                   crlf_bytes=data.count(b"\r\n"), utf8_replacement_sequences=data.count(b"\xef\xbf\xbd"),
                   invalid_utf8_rows=len(bad), replacement_character_rows=len(replacement),
                   id_column="job_id" if ids is not None else None,
                   duplicate_id_excess=sum(v-1 for v in ids.values()) if ids is not None else None,
                   missing={k: sum(not r[k].strip() for r in rows) for k in fields},
                   missing_literal_markers={k: sum(r[k].strip().casefold() in {"nan", "none", "null", "n/a"} for r in rows) for k in fields},
                   empty_json_lists={k: sum(r[k].strip() == "[]" for r in rows) for k in fields},
                   spreadsheet_error_cells={k: sum(bool(ERROR_CELL.search(r[k])) for r in rows) for k in fields},
                   site_counts=dict(Counter(r["site"] for r in rows)),
                   repeated_url_excess=sum(n-1 for n in Counter(r["job_url"] for r in rows).values()),
                   exact_text_duplicate_excess=sum(n-1 for n in exact.values()),
                   normalized_text_duplicate_excess=sum(n-1 for n in normalized.values()),
                   near_pairs_between_unique_texts=len(near), near_threshold=0.85,
                   near_interpretation="Diagnostic on corrupted decoded structure, not trustworthy content dedup" if bad or replacement
                   else "Lexical 3-token shingle Jaccard; not semantic duplicate certification")
    return rows, profile, dict(invalid_utf8_rows=bad, replacement_character_rows=replacement, near_pairs=near)


def unique_index(rows, key):
    values = {r[key]: r for r in rows}
    require(len(values) == len(rows) and all(values), f"Missing/duplicate {key}; cannot assume one-to-one stage linkage")
    return values


def reconcile(raw, clean, matching, pilot):
    cb, mb = unique_index(clean, "job_id"), unique_index(matching, "job_id")
    referenced, primary, lineage = set(), set(), []
    raw_changes = Counter()
    for clean_number, row in enumerate(clean, 1):
        refs = json.loads(row["source_records_json"])
        links = []
        for reference in refs:
            number = int(reference["source_row_number"])
            valid = 1 <= number <= len(raw)
            url_ok = valid and raw[number-1]["job_url"].strip() == reference["job_url"].strip()
            site_ok = valid and raw[number-1]["site"] == reference["site"]
            links.append(dict(raw_row=number, url_matches=url_ok, site_matches=site_ok,
                              evidence="declared source_row_number plus exact URL/site; raw text is not reconstructed"))
            if url_ok and site_ok:
                referenced.add(number)
        number = int(row["source_row_number"])
        primary.add(number)
        primary_ok = 1 <= number <= len(raw) and raw[number-1]["job_url"].strip() == row["job_url"].strip()
        changed = [k for k in raw[0] if primary_ok and raw[number-1][k] != row[k]]
        raw_changes.update(changed)
        match = mb.get(row["job_id"])
        lineage.append(dict(job_id=row["job_id"], clean_row=clean_number,
                            raw_primary_row=number, raw_primary_url_matches=primary_ok, raw_links=links,
                            raw_clean_changed_fields=changed,
                            raw_clean_reason="unknown; provided raw is corrupted and original transformation script is absent",
                            matching_present=match is not None,
                            clean_description_sha256=digest(row["description"]),
                            matching_declared_description_sha256=match["source_description_sha256"] if match else None,
                            clean_matching_hash_verified=bool(match and digest(row["description"]) == match["source_description_sha256"])))
    pilot_links = []
    for row in pilot:
        match = mb.get(row["job_id"])
        pilot_links.append(dict(job_id=row["job_id"], matching_present=match is not None,
                                pre_edit_hash_verified=bool(match and digest(match["match_text"]) == row["source_match_text_sha256"]),
                                changed_fields=[k for k in row if match and k in match and row[k] != match[k]]))
    shared = sorted(set(clean[0]) & set(matching[0]))
    clean_match_changes = [dict(job_id=jid, fields=[k for k in shared if cb[jid][k] != mb[jid][k]]) for jid in sorted(set(cb) & set(mb))]
    summary = dict(raw_to_clean=dict(raw_records=len(raw), clean_records=len(clean), referenced_raw_rows=len(referenced),
                                     primary_raw_rows=len(primary), merged_nonprimary_rows=len(referenced-primary),
                                     unlinked_raw_rows=sorted(set(range(1, len(raw)+1))-referenced),
                                     unlinked_description_lengths={str(i): len(raw[i-1]["description"]) for i in sorted(set(range(1, len(raw)+1))-referenced)},
                                     declared_duplicate_count=sum(int(r["duplicate_count"]) for r in clean),
                                     linked_references=sum(len(r["raw_links"]) for r in lineage),
                                     invalid_reference_links=sum(not (x["url_matches"] and x["site_matches"]) for r in lineage for x in r["raw_links"]),
                                     changed_primary_fields=dict(raw_changes),
                                     reason_status="38 merged source references and one short unlinked row observed; historical removal rationale not proven"),
                   clean_to_matching=dict(common_ids=len(set(cb) & set(mb)), added_ids=sorted(set(mb)-set(cb)),
                                          removed_ids=sorted(set(cb)-set(mb)),
                                          common_field_changes=sum(bool(r["fields"]) for r in clean_match_changes),
                                          verified_description_hashes=sum(r["clean_matching_hash_verified"] for r in lineage),
                                          mismatched_description_ids=[r["job_id"] for r in lineage if r["matching_present"] and not r["clean_matching_hash_verified"]]),
                   matching_to_pilot=dict(pilot_records=len(pilot), found=sum(r["matching_present"] for r in pilot_links),
                                          pre_edit_hash_verified=sum(r["pre_edit_hash_verified"] for r in pilot_links),
                                          changed_match_text=sum("match_text" in r["changed_fields"] for r in pilot_links)),
                   historical_pipeline_reproduced=False)
    return summary, lineage, pilot_links, clean_match_changes


def evidence(field, text, pattern):
    return [dict(field=field, start=m.start(), end=m.end(), text=m.group()) for m in re.finditer(pattern, text, re.I)]


def selection_features(row):
    title = row["title_for_matching"]
    role = []
    patterns = {
        "Data Analyst": r"data analyst|phân tích dữ liệu",
        "QA/Testing": r"\bqa\b|\bqc\b|tester|test engineer|kiểm thử|automation test",
        "DevOps": r"devops|site reliability|cloud engineer",
        "Frontend": r"front[ -]?end",
    }
    ev = {}
    for name, pattern in patterns.items():
        hits = evidence("title_for_matching", title, pattern)
        if hits:
            role.append(name)
            ev[name] = hits
    # Do not call every Python/Java keyword a backend role.
    if not role and not re.search(r"\b(?:ai|data|machine learning|manager|director|mobile|android)\b", title, re.I):
        for name, language in (("Backend Python", r"\bpython\b|django|fastapi|odoo"), ("Backend Java", r"\bjava\b|spring")):
            hits = evidence("title_for_matching", title, language)
            if hits and re.search(r"developer|engineer|backend|back.end|lập trình|phát triển", title, re.I):
                role.append(name)
                ev[name] = hits
    text = row["match_text"]
    vietnamese = evidence("match_text", text, r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")
    years = evidence("requirements_text", row["requirements_text"], r"\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+)?\s*\+?\s*(?:năm|years?|months?|tháng)\b")
    return dict(rule_version=VERSION, role_candidates=role, role_evidence=ev,
                vietnamese_signal=len(vietnamese) >= 20, vietnamese_character_hits=len(vietnamese),
                experience_mentions=years, experience_bucket=years[0]["text"].casefold() if years else "unknown",
                must_mentions=evidence("requirements_text", row["requirements_text"], r"bắt buộc|tối thiểu|ít nhất|must|required|at least|minimum"),
                preferred_present=bool(row["preferred_requirements_text"].strip()) and not ERROR_CELL.search(row["preferred_requirements_text"]),
                shared_keyword_mentions=evidence("match_text", text, r"\b(?:python|java|sql|docker|react|aws)\b")[:12],
                note="Literal cues for development sampling only; not skill proficiency, scoped months, mandatory truth or CV-JD labels")


def quality(row, lineage):
    reasons = []
    for field in PROFESSIONAL:
        if ERROR_CELL.search(row[field]):
            reasons.append("spreadsheet_error:" + field)
        if "\ufffd" in row[field]:
            reasons.append("replacement_character:" + field)
    if not lineage or not lineage["clean_matching_hash_verified"]:
        reasons.append("clean_description_hash_unverified")
    if not lineage or not lineage["raw_primary_url_matches"] or not all(x["url_matches"] and x["site_matches"] for x in lineage["raw_links"]):
        reasons.append("raw_source_identity_unverified")
    for field in ("tasks_text", "requirements_text"):
        if len(row[field].strip()) < 80:
            reasons.append("missing_or_short_section:" + field)
    if row["needs_review"].casefold() != "false":
        reasons.append("upstream_needs_review")
    if row["extraction_status"] != "sections_found":
        reasons.append("upstream_extraction:" + row["extraction_status"])
    return reasons


def select_batch(records, metadata, seed=20261113, per_role=12):
    """Prefer gate-passing rows; permit clearly labeled parser-review cases for shortages."""
    selected, used = [], set()
    availability = {}
    for role in ROLES:
        candidates = [r for r in records if not r["development_only"] and r["decision"] != "exclude_exact_duplicate"
                      and role in metadata[r["external_id"]]["role_candidates"]]
        # Never select broken match_text or unverified identity/hash, even for parser review.
        candidates = [r for r in candidates if not any(reason.startswith(("spreadsheet_error:match_text", "replacement_character",
                           "clean_description_hash_unverified", "raw_source_identity_unverified")) for reason in r["decision_reasons"])]
        availability[role] = dict(records=len(candidates), groups=len({r["group_id"] for r in candidates}),
                                  gate_passing=sum(r["decision"] == "keep" for r in candidates))
        covered = set()
        for _ in range(per_role):
            remaining = [r for r in candidates if r["group_id"] not in used]
            if not remaining:
                break
            def order(r):
                f = metadata[r["external_id"]]
                diversity = {"exp:" + f["experience_bucket"], "preferred:" + str(f["preferred_present"]),
                             "must:" + str(bool(f["must_mentions"]))}
                return (r["decision"] != "keep", not f["vietnamese_signal"], -len(diversity-covered), digest(f"{seed}|{role}|{r['record_id']}"))
            row = min(remaining, key=order)
            f = metadata[row["external_id"]]
            used.add(row["group_id"])
            covered.update({"exp:" + f["experience_bucket"], "preferred:" + str(f["preferred_present"]), "must:" + str(bool(f["must_mentions"]))})
            selected.append(dict(job_id=row["external_id"], record_id=row["record_id"], group_id=row["group_id"], role=role,
                                 purpose="development/parser; not final test", gate_decision=row["decision"],
                                 selection_reason="one per non-pilot group; passing quality gate first, Vietnamese cue, diversity, seeded tie break",
                                 quality_reasons=row["decision_reasons"], **f))
    return selected, availability


def prepare_upstream(source_dir, output, seed=20261113):
    source_dir = Path(source_dir).resolve()
    paths = [source_dir / name for name in FILES]
    original_hashes = {p.name: file_hash(p) for p in paths}
    stages, profiles, diagnostics = {}, {}, {}
    for path in paths:
        stages[path.name], profiles[path.name], diagnostics[path.name] = read_stage(path)
    raw, clean, matching = (stages[name] for name in FILES)
    # Only the two valid UTF-8 stages may supply canonical text.
    require(all(profiles[name]["invalid_utf8_rows"] == 0 for name in FILES[1:]), "Clean/matching decoding is unresolved")
    _, pilot = csv_rows(ROOT / "jobapply_pilot_v1/jobs_pilot.csv")
    relations, lineage, pilot_links, changes = reconcile(raw, clean, matching, pilot)
    links = {r["job_id"]: r for r in lineage}
    cb = unique_index(clean, "job_id")
    require(set(cb) == {r["job_id"] for r in matching}, "Stage ID sets differ; reconcile additions/removals before canonical import")
    canonical, metadata = [], {}
    for row in matching:
        jid = row["job_id"]
        features = selection_features(row)
        metadata[jid] = features
        refs = json.loads(cb[jid]["source_records_json"])
        canonical.append(dict(**row, import_exposure="prospective", import_quality_reasons=json.dumps(quality(row, links.get(jid))),
                              import_related_sources=json.dumps(sorted({"url:" + digest(r["job_url"].strip()) for r in refs})),
                              import_lineage=json.dumps(links[jid], ensure_ascii=False),
                              import_role=features["role_candidates"][0] if len(features["role_candidates"]) == 1 else ""))
    spec = dict(kind="jd", namespace="it-job-posting-matching", version="sha256:" + original_hashes[FILES[2]],
                path="canonical_jd.csv", columns=dict(external_id="job_id", text="match_text", source_group="content_group_id",
                    role="import_role", quality_reasons="import_quality_reasons", related_source_keys="import_related_sources",
                    lineage="import_lineage", exposure="import_exposure"),
                defaults=dict(is_synthetic=False, text_scope="professional"),
                source_url="https://github.com/SonPhatTranDeveloper/IT-Job-Posting",
                source_attribution_status="URL from repository historical report, not independently verified source revision",
                collected_at=None, usage_terms=None)
    records = [record(row, spec) for row in canonical]
    anchors, _ = pilot_anchors()
    group_records(records, anchors)
    selected, availability = select_batch(records, metadata, seed)
    selected_groups = {r["group_id"] for r in selected}
    development_ids = {r["external_id"] for r in records if r["group_id"] in selected_groups}
    preselection_pilot_ids = {r["external_id"] for r in records if r["development_only"]}
    for row in canonical:
        if row["job_id"] in development_ids:
            row["import_exposure"] = "development"
    folder = fresh_folder(output)
    (folder / "snapshots").mkdir()
    for path in paths:
        require(file_hash(path) == original_hashes[path.name], "Upstream source changed during audit")
        shutil.copyfile(path, folder / "snapshots" / path.name)
    write_json(folder / "profiles.json", profiles)
    write_json(folder / "diagnostics.json", diagnostics)
    write_json(folder / "relations.json", relations)
    write_lines(folder / "lineage.jsonl", lineage)
    write_json(folder / "pilot_links.json", pilot_links)
    write_json(folder / "clean_matching_changes.json", changes)
    write_json(folder / "selection_features.json", metadata)
    write_json(folder / "selection.json", selected)
    write_csv(folder / "canonical_jd.csv", canonical, list(canonical[0]))
    config = dict(schema_version=1, dataset_version="upstream-jd-observation-v1-" + original_hashes[FILES[2]][:12],
                  adapter_version=VERSION, near_threshold=0.85, sources=[spec],
                  context_files=[dict(path="snapshots/" + name, role="upstream_stage_not_additional_records") for name in FILES]
                  + [dict(path=name, role="lineage_quality_selection_evidence") for name in ("profiles.json", "relations.json", "lineage.jsonl", "selection_features.json", "selection.json")])
    write_json(folder / "import_config.json", config)
    result = ingest(folder / "import_config.json", folder / "dataset")
    final_records = read_lines(folder / "dataset/records.jsonl")
    batch_summary = dict(total=len(selected), seed=seed, target_per_role=12, actual_by_role=dict(Counter(r["role"] for r in selected)),
                         available=availability, shortages={role: 12-sum(r["role"] == role for r in selected) for role in ROLES
                                                           if sum(r["role"] == role for r in selected) < 12},
                         gate_decisions=dict(Counter(r["gate_decision"] for r in selected)),
                         vietnamese_signal=sum(r["vietnamese_signal"] for r in selected),
                         experience_mentions=sum(bool(r["experience_mentions"]) for r in selected),
                         preferred_present=sum(r["preferred_present"] for r in selected),
                         must_mentions=sum(bool(r["must_mentions"]) for r in selected),
                         development_group_closure=len(development_ids), purpose="development/parser only")
    summary = dict(version=VERSION, source_hashes=original_hashes, profiles=profiles, relations=relations, import_summary=result,
                   quality_reason_counts=dict(Counter(reason for r in final_records if r["decision"] == "quarantine" for reason in r["decision_reasons"])),
                   pilot_related_records_before_selection=len(preselection_pilot_ids), pilot_related_ids=sorted(preselection_pilot_ids),
                   decisions_by_exposure={str(dev): dict(Counter(r["decision"] for r in final_records if r["development_only"] == dev)) for dev in (True, False)},
                   batch=batch_summary, history_reconstructed=False, split_locked=False, cv_jd_labels_created=0,
                   observed_pipeline_versions=dict(Counter(r["pipeline_version"] for r in matching)),
                   unknown=["Exact original raw encoding/text before corruption", "Original cleaning/section code and source revision",
                            "Collection dates and redistribution terms"])
    write_json(folder / "summary.json", summary)
    require(all(file_hash(p) == original_hashes[p.name] for p in paths), "Original bytes changed")
    seal(folder, "upstream", dict(adapter_version=VERSION, source_hashes=original_hashes, canonical_stage="matching with conservative quality gate; text unchanged",
                                  raw_corruption_not_repaired=True, scope="development preparation; no formal split, labels or training"))
    return summary
