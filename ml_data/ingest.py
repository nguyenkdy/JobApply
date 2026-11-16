"""Explicit CSV column mapping; retain raw sources and unknown metadata."""
import os
from pathlib import Path
import shutil
import subprocess

from .common import (ROOT, MIN_PROFESSIONAL_BODY_CHARS, csv_rows, digest, distribution, file_hash, fresh_folder,
                     normalize, read_json, require, seal, write_json, write_lines)
from .grouping import group_records

FIELDS = {"external_id", "text", "source_group", "template_group", "role", "skills", "stack",
          "experience", "is_synthetic", "exposure", "text_scope", "upstream_text_sha256",
          "quality_reasons", "related_source_keys", "lineage"}
UPSTREAM = ("job_descriptions.csv", "jobs_clean.csv", "jobs_matching.csv")


def inventory(workspace, output):
    workspace = Path(workspace).resolve()
    found = {name: [] for name in UPSTREAM}
    errors, excluded, scripts = [], [], []
    def onerror(exc):
        errors.append(dict(path=str(exc.filename), error=type(exc).__name__))
    for base, dirs, names in os.walk(workspace, onerror=onerror, followlinks=False):
        for name in list(dirs):
            path = Path(base) / name
            if (name in {".git", "node_modules", "__pycache__", ".tools", ".test-data", ".ruff_cache", ".pytest_cache", "ml_data_runs", "reruns"}
                    or name.startswith((".venv", "pytest-cache-files-")) or path.is_symlink()):
                dirs.remove(name)
                excluded.append(path.relative_to(workspace).as_posix())
        for name in names:
            path = Path(base) / name
            if name in found:
                info = dict(path=path.relative_to(workspace).as_posix(), sha256=file_hash(path), bytes=path.stat().st_size)
                try:
                    columns, rows = csv_rows(path)
                    info.update(columns=columns, rows=len(rows))
                except UnicodeError as exc:
                    import csv
                    import io
                    reader = csv.DictReader(io.StringIO(path.read_bytes().decode("utf-8-sig", errors="surrogateescape"), newline=""), strict=True)
                    rows = list(reader)
                    info.update(columns=reader.fieldnames or [], rows=len(rows), encoding_error=str(exc))
                except ValueError as exc:
                    info["parse_error"] = str(exc)
                found[name].append(info)
            if path.suffix in {".py", ".ipynb"} and path != Path(__file__):
                content = path.read_text(encoding="utf-8-sig", errors="replace")
                refs = [name for name in UPSTREAM if name in content]
                if refs:
                    scripts.append(dict(path=path.relative_to(workspace).as_posix(), sha256=file_hash(path), mentions=refs,
                                        note="Text reference only; not proof this script created an upstream file"))
    tracked = subprocess.run(["git", "-C", str(workspace), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    processing = []
    for name in tracked:
        path = workspace / name
        if path.suffix == ".py" and name.startswith("jobapply_pilot_v1/") and path.is_file():
            processing.append(dict(path=name, sha256=file_hash(path)))
    counts_ok = (all(found[name] for name in UPSTREAM)
                 and found["job_descriptions.csv"][0].get("rows") == 3101
                 and found["jobs_clean.csv"][0].get("rows") == 3062
                 and found["jobs_matching.csv"][0].get("rows") == 3062)
    result = dict(scope="Local workspace, including ignored data; excluded dependency/cache/run directories listed explicitly",
                  upstream=found, missing=[name for name in UPSTREAM if not found[name]],
                  tracked_upstream=[name for name in tracked if Path(name).name in UPSTREAM],
                  scripts_referencing_upstream=sorted(scripts, key=lambda r: r["path"]),
                  tracked_pilot_processing_scripts=processing,
                  excluded_directories=sorted(excluded), scan_errors=errors,
                  historical_counts_verified=counts_ok,
                  note="Row counts verified from local files when present; original cleaning/section scripts remain absent.")
    folder = fresh_folder(output)
    write_json(folder / "inventory.json", result)
    seal(folder, "inventory", dict(scope=result["scope"]))
    return result


def boolean(value):
    if isinstance(value, bool) or value is None:
        return value
    require(str(value).casefold() in {"true", "false", ""}, "is_synthetic requires true/false or empty")
    return None if value == "" else str(value).casefold() == "true"


def terms(value):
    if value in (None, ""):
        return []
    require(isinstance(value, (list, str)), "skills/stack need a list or semicolon-separated string")
    values = value.split(";") if isinstance(value, str) else value
    require(all(isinstance(v, str) for v in values), "skill/stack values must be strings")
    return sorted({normalize(v).casefold() for v in values if v.strip()})


def experience(value):
    import json
    if value in (None, ""):
        return {}
    values = json.loads(value) if isinstance(value, str) else value
    require(isinstance(values, dict), "experience must be JSON scope -> non-negative integer months")
    require(all(isinstance(k, str) and k.strip() and type(v) is int and v >= 0 for k, v in values.items()),
            "Invalid scoped months; unknown must be omitted, not replaced by zero")
    normalized = {normalize(k).casefold(): v for k, v in values.items()}
    require(len(normalized) == len(values), "Duplicate experience scopes after normalization")
    return normalized


def record(raw, spec):
    import json
    fields = spec.get("columns", {})
    defaults = spec.get("defaults", {})
    require(set(fields) <= FIELDS and set(defaults) <= FIELDS, "Unknown mapping/default field")
    require(all(column in raw for column in fields.values()), "Mapped column missing from source CSV")
    value = {**defaults, **{name: raw[column] for name, column in fields.items()}}
    text = value.get("text", "")
    require(isinstance(text, str), "text must be a CSV string")
    normalized = normalize(text)
    external_id = str(value.get("external_id", "")).strip()
    entity_key = external_id or digest(normalized.casefold())
    entity_id = spec["kind"] + "_" + digest(spec["namespace"] + "|" + entity_key)[:32]
    raw_hash = digest(text)
    result = dict(record_id=entity_id + "_" + raw_hash[:24], entity_id=entity_id,
                  kind=spec["kind"], external_id=external_id, namespace=spec["namespace"],
                  text_original=text, text_normalized=normalized, text_sha256=raw_hash,
                  normalized_text_sha256=digest(normalized),
                  normalized_sha256=digest(normalized.casefold()),
                  source_group=str(value.get("source_group", "")).strip(),
                  template_group=str(value.get("template_group", "")).strip(),
                  role=normalize(value.get("role", "")).casefold(), skills=terms(value.get("skills")),
                  stack=terms(value.get("stack")), experience=experience(value.get("experience")),
                  is_synthetic=boolean(value.get("is_synthetic")), exposure=value.get("exposure", "development"),
                  text_scope=value.get("text_scope", "unreviewed"),
                  upstream_text_sha256=value.get("upstream_text_sha256", ""),
                  metadata_status="source_asserted_not_independently_verified", missing_fields=[],
                  decision="keep", decision_reasons=[], occurrences=[])
    require(result["exposure"] in {"development", "prospective"}, "exposure must be development or prospective")
    require(result["text_scope"] in {"professional", "unreviewed"}, "text_scope must be professional or unreviewed")
    for key in ("external_id", "source_group", "template_group", "role", "skills", "stack", "experience"):
        if not result[key]:
            result["missing_fields"].append(key)
    if result["is_synthetic"] is None:
        result["missing_fields"].append("is_synthetic")
    if "exposure" not in value:
        result["missing_fields"].append("exposure_defaulted_development")
    if len(normalized) < MIN_PROFESSIONAL_BODY_CHARS:
        result["decision_reasons"].append(f"empty_or_short_text_under_{MIN_PROFESSIONAL_BODY_CHARS}_chars")
    if result["text_scope"] != "professional":
        result["decision_reasons"].append("professional_text_not_confirmed; no automatic PII/section extraction")
    if result["kind"] == "cv":
        if not result["source_group"]:
            result["decision_reasons"].append("missing_CV_source_lineage")
        if result["is_synthetic"] is None:
            result["decision_reasons"].append("CV_synthetic_status_unknown")
        if result["is_synthetic"] and not result["template_group"]:
            result["decision_reasons"].append("synthetic_CV_template_lineage_unknown")
    if result["decision_reasons"]:
        result["decision"] = "quarantine"
    for name, default, expected_type in (("quality_reasons", [], list), ("related_source_keys", [], list), ("lineage", {}, dict)):
        field = value.get(name, default)
        field = json.loads(field) if isinstance(field, str) else field
        require(isinstance(field, expected_type), f"Invalid {name}")
        if name == "lineage" and "template_ancestors" in field:
            inherited = field["template_ancestors"]
            require(isinstance(inherited, list) and all(isinstance(x, str) and x.strip() for x in inherited),
                    "template_ancestors must be a list of nonempty historical group keys")
        if expected_type is list:
            require(all(isinstance(item, str) and item.strip() for item in field), f"Invalid {name} entries")
        if name == "quality_reasons" and field:
            result["decision"] = "quarantine"
            result["decision_reasons"].extend(field)
        elif name != "quality_reasons":
            result[name] = field
    return result


def pilot_anchors():
    """Always protect the viewed pilot, including IDs and pre-edit JD text hashes."""
    anchors, files = [], []
    for kind, name, id_col, text_col in (("cv", "cvs_synthetic.csv", "cv_id", "cv_text"),
                                        ("jd", "jobs_pilot.csv", "job_id", "match_text")):
        path = ROOT / "jobapply_pilot_v1" / name
        _, rows = csv_rows(path)
        files.append(path)
        for raw in rows:
            row = record(raw, dict(kind=kind, namespace="protected_pilot", columns=dict(external_id=id_col, text=text_col),
                                  defaults=dict(exposure="development", text_scope="professional")))
            row.update(record_id="PILOT_" + raw[id_col], protected_pilot=True,
                       upstream_text_sha256=raw.get("source_match_text_sha256", ""),
                       source_group=raw.get("content_group_id", ""),
                       related_source_keys=["url:" + digest(raw["job_url"].strip())] if raw.get("job_url") else [])
            anchors.append(row)
    return anchors, files


def ingest(config_path, output):
    config_path = Path(config_path).resolve()
    config = read_json(config_path)
    require(config.get("schema_version") == 1 and config.get("sources"), "Expected schema_version=1 and nonempty sources")
    require(isinstance(config.get("dataset_version"), str) and config["dataset_version"].strip(), "Missing dataset_version")
    threshold = config.get("near_threshold", 0.85)
    require(type(threshold) in (int, float) and 0 < threshold <= 1, "Invalid near_threshold")
    rows_by_id, sources = {}, []
    for number, spec in enumerate(config["sources"]):
        require(spec.get("kind") in {"cv", "jd"}, "Source kind must be cv/jd")
        require(isinstance(spec.get("namespace"), str) and spec["namespace"].strip(), "Stable source namespace required")
        require(isinstance(spec.get("version"), str) and spec["version"].strip(), "Source version required")
        path = (config_path.parent / spec["path"]).resolve()
        columns, rows = csv_rows(path)
        receipt = dict(snapshot=f"raw/{number:03d}.csv", sha256=file_hash(path), bytes=path.stat().st_size,
                       input_path=spec["path"], namespace=spec["namespace"], version=spec["version"], rows=len(rows), columns=columns,
                       source_url=spec.get("source_url"), collected_at=spec.get("collected_at"),
                       usage_terms=spec.get("usage_terms"),
                       missing_source_metadata=[k for k in ("source_url", "collected_at", "usage_terms") if not spec.get(k)])
        sources.append((path, receipt))
        for row_number, raw in enumerate(rows, 1):
            row = record(raw, spec)
            occurrence = dict(source_snapshot=receipt["snapshot"], source_file_sha256=receipt["sha256"],
                              source_version=spec["version"], row_number=row_number, raw_row=raw)
            if row["record_id"] in rows_by_id:
                previous = rows_by_id[row["record_id"]]
                require({k: v for k, v in previous.items() if k != "occurrences"} == {k: v for k, v in row.items() if k != "occurrences"},
                        "Same entity/text has conflicting metadata; reconcile mappings before import")
                previous["occurrences"].append(occurrence)
            else:
                row["occurrences"].append(occurrence)
                rows_by_id[row["record_id"]] = row
    require(rows_by_id, "All input tables are empty")
    records = sorted(rows_by_id.values(), key=lambda r: r["record_id"])
    anchors, pilot_files = pilot_anchors()
    history_files = []
    for index, spec in enumerate(config.get("historical_cv_sources", [])):
        require(spec["kind"] == "cv", "Historical development anchors must be CV sources")
        path = (config_path.parent / spec["path"]).resolve()
        _, history = csv_rows(path)
        for raw in history:
            anchor = record(raw, spec)
            anchor.update(record_id=f"HISTORY_{index}_" + anchor["record_id"], protected_pilot=True,
                          exposure="development", protected_reference_type="historical_cv_development")
            anchors.append(anchor)
        history_files.append(path)
    groups, edges = group_records(records, anchors, threshold)
    contexts = []
    for index, item in enumerate(config.get("context_files", [])):
        path = (config_path.parent / item["path"]).resolve()
        contexts.append((path, dict(snapshot=f"context/{index:03d}{path.suffix}", role=item["role"],
                                    sha256=file_hash(path), input_path=item["path"])))
    folder = fresh_folder(output)
    (folder / "raw").mkdir()
    (folder / "protected_pilot").mkdir()
    for path, receipt in sources:
        shutil.copyfile(path, folder / receipt["snapshot"])
        require(file_hash(folder / receipt["snapshot"]) == receipt["sha256"], "Source changed during import")
    for path in pilot_files:
        shutil.copyfile(path, folder / "protected_pilot" / path.name)
    if history_files:
        (folder / "protected_history").mkdir()
        for index, path in enumerate(history_files):
            shutil.copyfile(path, folder / "protected_history" / f"{index:03d}.csv")
    if contexts:
        (folder / "context").mkdir()
        for path, receipt in contexts:
            shutil.copyfile(path, folder / receipt["snapshot"])
            require(file_hash(folder / receipt["snapshot"]) == receipt["sha256"], "Context source changed during import")
        write_json(folder / "context_sources.json", [receipt for _, receipt in contexts])
    write_json(folder / "config.json", config)
    write_json(folder / "sources.json", [receipt for _, receipt in sources])
    write_lines(folder / "records.jsonl", records)
    write_json(folder / "groups.json", groups)
    write_lines(folder / "group_edges.jsonl", edges)
    write_lines(folder / "protected_anchors.jsonl", anchors)
    summary = dict(dataset_version=config["dataset_version"], records=len(records),
                   source_rows=sum(r["rows"] for _, r in sources), duplicate_occurrences=sum(len(r["occurrences"])-1 for r in records),
                   groups=len(groups), development_groups=sum(g["development_only"] for g in groups),
                   distribution=distribution(records), labels_created=0, final_test_ready=False,
                   limitations=["Lexical near-duplicate heuristic, not semantic paraphrase detection",
                                "Source metadata/lineage and professional-text claim need review; not a privacy certifier",
                                "No upstream cleaning history reconstructed; raw sources preserved byte-for-byte"])
    write_json(folder / "summary.json", summary)
    seal(folder, "dataset", dict(dataset_version=config["dataset_version"], near_threshold=threshold,
                                  minimum_professional_body_chars=MIN_PROFESSIONAL_BODY_CHARS,
                                  normalization="NFKC, whitespace per line, blank lines omitted; dedup casefold; v1",
                                  label_status="unlabeled; source labels untouched", ranking_k=5))
    return summary
