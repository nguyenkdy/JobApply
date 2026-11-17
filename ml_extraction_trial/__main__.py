"""Prepare baseline extraction trials or validate externally supplied candidate outputs. No API calls."""
import argparse
from collections import Counter
from pathlib import Path
import platform
import shutil
import sys

from ml_data import technical_policy_v2 as v2
from ml_data.policies import technical_v3 as v3
from ml_data.common import ROOT, csv_rows, file_hash, fresh_folder, read_json, read_lines, require, seal, verify, write_json, write_lines
from ml_data.input_contract import verify_inputs, verify_execution_contract
from ml_data.policies.__main__ import fingerprints
from .contract import VERSION, PROMPT, schema, source_hash, validate
from .fixtures import cases, score

TYPE = "structured-extraction-trial-v1"


def quote_ref(span, document):
    field = span.get("field", "cv_text")
    text, quote = document["fields"][field], span["quote"]
    require(text[span["start"]:span["end"]] == quote, "Baseline evidence offset differs")
    starts, position = [], 0
    while True:
        position = text.find(quote, position)
        if position < 0:
            break
        starts.append(position)
        position += 1
    return dict(field=field, quote=quote, occurrence=starts.index(span["start"]))


def baseline(document, facts):
    claims = []
    def add(kind, value, span, modality, polarity="affirmative"):
        claims.append(dict(kind=kind, value=value, evidence=[quote_ref(span, document)], modality=modality, polarity=polarity))
    for key, span in facts["skills"].items():
        add("skill", dict(name=key), span, "observed" if document["kind"] == "cv" else "unknown")
    for family, spans in facts["functions"].items():
        for span in spans:
            add("task", dict(family=family, description=span["quote"]), span, "observed")
    if document["kind"] == "cv":
        for d in facts["durations"]:
            add("experience", dict(scope=d["scope"], minimum_months=d["months"], maximum_months=d["months"], operator="exact",
                experience_kind=d["kind"] if d["kind"] in {"employment", "contract", "internship", "project"} else "unspecified"), d, "observed")
        for key, span in facts["nonuse"].items():
            add("skill", dict(name=key), span, "observed", "negated")
    else:
        for c in facts["clauses"]:
            if c["state"] == "mandatory":
                add("logic", c["tree"], c["evidence"], "required")
            elif c["state"] == "duration":
                d = c["duration"]
                add("experience", dict(scope=d["scope"], minimum_months=d["months"], maximum_months=d["range_upper_months"],
                    operator="range" if d["range_upper_months"] is not None else "strict_minimum" if d["strict"] else "minimum",
                    experience_kind="unspecified"), c["evidence"], "required")
    response = dict(schema_version=VERSION, document_id=document["document_id"], source_sha256=document["source_sha256"],
        coverage={f: "partial" for f in document["fields"]}, claims=claims)
    validate(response, document)
    return response


def fixture_baseline(document):
    record = dict(role="", role_precision="unknown_or_conflicting", text_sha256=document["source_sha256"],
        benchmark_scope="requires_protocol_mapping", occurrences=[dict(raw_row=document["fields"])])
    return baseline(document, v3.jd_facts(v2.jd_facts(record)))


def inputs(inventory):
    verify(inventory, "document-evidence-inventory")
    receipt = read_json(inventory / "input_receipt.json")
    parent = ROOT / receipt["parent_path"]
    require(file_hash(parent / "manifest.json") == receipt["parent_manifest_sha256"], "Inventory parent changed")
    verify(parent, "development-label-revision-v3")
    verify_execution_contract(read_json(parent / "execution_fingerprints.json"), fingerprints())
    require(file_hash(parent / "labels.csv") == receipt["parent_labels_sha256"], "Labels changed")
    v2_receipt = read_json(parent / "input_receipt.json")
    old = ROOT / v2_receipt["parent_path"]
    require(file_hash(old / "manifest.json") == v2_receipt["parent_manifest_sha256"], "v2 parent changed")
    verify(old, "development-label-revision")
    links = read_json(old / "input_receipt.json")
    intake, audit = ROOT / links["intake_path"], ROOT / links["audit_path"]
    require(file_hash(intake / "manifest.json") == receipt["intake_manifest_sha256"] == links["intake_manifest_sha256"], "Intake changed")
    require(file_hash(audit / "manifest.json") == links["audit_manifest_sha256"], "Audit changed")
    require(verify_inputs(intake, audit) == read_json(parent / "input_contract.json"), "Protected originals changed")
    return parent, intake


def select(inventory, records):
    chosen = {}
    for r in read_lines(inventory / "extraction_probe_set.jsonl"):
        chosen.setdefault(r["record_id"], []).append("duration_probe:"+r["reason"])
    rows = csv_rows(inventory / "record_inventory.csv")[1]
    for kind in ("cv", "jd"):
        task_gaps = sorted((r for r in rows if r["kind"] == kind and int(r["task_action_cues"]) > 0 and int(r["task_functions_parsed"]) == 0), key=lambda r: r["record_id"])
        for r in task_gaps[:5]:
            chosen.setdefault(r["record_id"], []).append("action_cue_without_task_function")
    for r in sorted((r for r in rows if r["kind"] == "jd" and r["role_parsed"] == "False"), key=lambda r: r["record_id"])[:5]:
        chosen.setdefault(r["record_id"], []).append("unresolved_occupation")
    result = []
    for rid, reasons in sorted(chosen.items()):
        r = records[rid]
        fields = {"cv_text": r["text_original"]} if r["kind"] == "cv" else {f: v2.source_field(r, f) for f in ("title_for_matching", "tasks_text", "requirements_text", "preferred_requirements_text")}
        result.append(dict(document_id=rid, kind=r["kind"], fields=fields, source_sha256=source_hash(fields),
            original_text_sha256=r["text_sha256"], group_id=r["group_id"], exposure="development", selection_reasons=reasons,
            origin="frozen_real_corpus" if r["kind"] == "jd" else "frozen_synthetic_cv"))
    return result


def summarize(documents, fixtures, fixture_results):
    return dict(version=VERSION, documents=len(documents), by_kind=dict(Counter(d["kind"] for d in documents)), fixtures=len(fixtures),
        baseline_fixture_assertions=score(fixtures, fixture_results), candidate_status="not_run_missing_model_endpoint_configuration",
        baseline_source="Real corpus: frozen v3 facts include upstream metadata and authored CV annotations; not a text-only end-to-end baseline. Fixtures: v3 JD parsing functions.",
        comparison_limit="A future text-only LLM and metadata-assisted corpus baseline do not have equivalent inputs. No corpus semantic accuracy measured.",
        labels_changed=0, models_trained=0, external_api_calls=0, gold=False, independent_evaluation=False)


def prepare(inventory, output):
    inventory = Path(inventory).resolve()
    parent, intake = inputs(inventory)
    parent_hash = file_hash(parent / "manifest.json")
    documents = select(inventory, {r["record_id"]: r for r in read_lines(intake / "records.jsonl")})
    fixtures = cases()
    facts = read_json(parent / "cv_facts.json") | read_json(parent / "jd_facts.json")
    original = [baseline(d, facts[d["document_id"]]) for d in documents]
    fixture_results = [fixture_baseline(d) for d in fixtures]
    folder = fresh_folder(output, (inventory, parent, intake))
    write_lines(folder / "documents.jsonl", documents)
    write_lines(folder / "fixtures.jsonl", fixtures)
    # Assertions/origin/selection reasons are withheld from candidate requests.
    write_lines(folder / "requests.jsonl", [{k: d[k] for k in ("document_id", "kind", "fields", "source_sha256")} for d in documents+fixtures])
    write_lines(folder / "baseline.jsonl", original+fixture_results)
    write_json(folder / "schema.json", schema())
    (folder / "prompt.txt").write_text(PROMPT, encoding="utf-8", newline="\n")
    summary = summarize(documents, fixtures, fixture_results)
    write_json(folder / "summary.json", summary)
    write_json(folder / "runtime.json", dict(python=sys.version, platform=platform.platform(), dependencies="standard library only"))
    write_json(folder / "input_receipt.json", dict(inventory_path=inventory.relative_to(ROOT).as_posix(), inventory_manifest_sha256=file_hash(inventory / "manifest.json"),
        parent_path=parent.relative_to(ROOT).as_posix(), parent_manifest_sha256=parent_hash,
        prompt_sha256=file_hash(folder / "prompt.txt"), schema_sha256=file_hash(folder / "schema.json")))
    shutil.copytree(Path(__file__).parent, folder / "trial_source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    require(inputs(inventory) == (parent, intake) and file_hash(parent / "manifest.json") == parent_hash, "Inputs changed")
    seal(folder, TYPE, dict(labels_changed=0, candidate_executed=False))
    return summary


def check(trial):
    trial = Path(trial).resolve()
    verify(trial, TYPE)
    receipt = read_json(trial / "input_receipt.json")
    inventory = ROOT / receipt["inventory_path"]
    require(file_hash(inventory / "manifest.json") == receipt["inventory_manifest_sha256"], "Inventory changed")
    parent, intake = inputs(inventory)
    require(file_hash(parent / "manifest.json") == receipt["parent_manifest_sha256"], "Parent changed")
    archived = {p.name: p.read_bytes().replace(b"\r\n", b"\n") for p in (trial / "trial_source").glob("*.py")}
    require(archived == {p.name: p.read_bytes().replace(b"\r\n", b"\n") for p in Path(__file__).parent.glob("*.py")}, "Trial source changed")
    documents = select(inventory, {r["record_id"]: r for r in read_lines(intake / "records.jsonl")})
    fixtures = cases()
    require(read_lines(trial / "documents.jsonl") == documents and read_lines(trial / "fixtures.jsonl") == fixtures, "Documents/fixtures differ")
    expected_requests = [{k: d[k] for k in ("document_id", "kind", "fields", "source_sha256")} for d in documents+fixtures]
    require(read_lines(trial / "requests.jsonl") == expected_requests, "Request leaked assertions or changed input")
    facts = read_json(parent / "cv_facts.json") | read_json(parent / "jd_facts.json")
    fixture_results = [fixture_baseline(d) for d in fixtures]
    require(read_lines(trial / "baseline.jsonl") == [baseline(d, facts[d["document_id"]]) for d in documents]+fixture_results, "Baseline differs")
    require(read_json(trial / "summary.json") == summarize(documents, fixtures, fixture_results), "Summary differs")
    require((trial / "prompt.txt").read_text(encoding="utf-8") == PROMPT and read_json(trial / "schema.json") == schema(), "Prompt/schema differs")
    require(file_hash(trial / "prompt.txt") == receipt["prompt_sha256"] and file_hash(trial / "schema.json") == receipt["schema_sha256"], "Contract hash differs")
    return dict(verified=True, documents=len(documents), fixtures=len(fixtures), candidate_executed=False)


def ingest(trial, responses, metadata, output):
    trial = Path(trial).resolve()
    check(trial)
    meta = read_json(metadata)
    for key in ("provider", "model", "revision", "prompt_sha256", "schema_sha256"):
        require(isinstance(meta.get(key), str) and bool(meta[key].strip()), "Missing inference provenance: "+key)
    require(isinstance(meta.get("settings"), dict), "Inference settings required")
    require(meta["prompt_sha256"] == file_hash(trial / "prompt.txt") and meta["schema_sha256"] == file_hash(trial / "schema.json"), "Prompt/schema version mismatch")
    docs = read_lines(trial / "documents.jsonl") + read_lines(trial / "fixtures.jsonl")
    by_id = {d["document_id"]: d for d in docs}
    candidate = read_lines(responses)
    require(len(candidate) == len(by_id) and len({r["document_id"] for r in candidate}) == len(candidate), "Missing/duplicate responses")
    require({r["document_id"] for r in candidate} == set(by_id), "Response document set differs")
    resolved = [validate(r, by_id[r["document_id"]]) for r in candidate]
    folder = fresh_folder(output, (trial, Path(responses).resolve(), Path(metadata).resolve()))
    shutil.copyfile(responses, folder / "raw_responses.jsonl")
    shutil.copyfile(metadata, folder / "inference_metadata.json")
    write_lines(folder / "resolved_evidence.jsonl", resolved)
    result = dict(candidate_status="externally_supplied_outputs_validated", provenance="Supplied model identity/settings retained, not independently authenticated",
        structural_and_quote_valid=len(resolved), semantic_correctness="not_established", coverage_verified=False,
        fixture_assertions=score(read_lines(trial / "fixtures.jsonl"), candidate), labels_changed=0, models_trained=0,
        trial_manifest_sha256=file_hash(trial / "manifest.json"), raw_response_sha256=file_hash(responses))
    write_json(folder / "summary.json", result)
    shutil.copytree(Path(__file__).parent, folder / "trial_source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    seal(folder, "structured-extraction-candidate-v1", dict(labels_changed=0))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("ingest")
    for name in ("trial", "responses", "metadata", "output"):
        p.add_argument("--"+name, type=Path, required=True)
    p = commands.add_parser("check")
    p.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.inventory, args.output))
    elif args.command == "check":
        print(check(args.artifact))
    else:
        print(ingest(args.trial, args.responses, args.metadata, args.output))
