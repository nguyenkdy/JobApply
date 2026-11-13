"""TEST ONLY upstream fixtures; no new CV-JD labels."""
import csv
import json

from _support import WorkspaceTest
from ml_data.common import digest, file_hash, read_json, verify
from ml_data.ingest import record
from ml_data.grouping import group_records
from ml_data.upstream import (PROFESSIONAL, quality, read_stage, reconcile, select_batch, selection_features,
                              prepare_upstream)


class UpstreamTests(WorkspaceTest):
    def rows(self):
        description = "TEST ONLY professional duties build services and APIs. " * 4
        raw = dict(title="Python Backend Developer", company="TEST", description=description, site="TEST", job_url="https://example.invalid/job/1")
        clean = dict(**raw, job_id="TEST_JOB", source_row_number="1", content_group_id="TEST_GROUP", duplicate_count="0",
                     source_records_json=json.dumps([dict(source_row_number=1, site="TEST", job_url=raw["job_url"])]))
        matching = {k: v for k, v in clean.items() if k not in {"description", "source_records_json", "duplicate_count"}}
        matching.update(title_for_matching=raw["title"], tasks_text=description, requirements_text=description,
                        preferred_requirements_text="", unclassified_professional_text="", match_text=description,
                        extraction_status="sections_found", needs_review="FALSE", human_reviewed="FALSE",
                        review_flags_json="[]", source_description_sha256=digest(description), pipeline_version="TEST_ONLY")
        return raw, clean, matching

    def save(self, name, rows):
        path = self.folder / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_corrupt_utf8_is_preserved_and_never_repaired(self):
        raw, _, _ = self.rows()
        path = self.save("raw.csv", [raw])
        path.write_bytes(path.read_bytes().replace(b"TEST ONLY", b"TEST\xfd\xef\xbf\xbd ONLY", 1))
        original = file_hash(path)
        rows, profile, details = read_stage(path)
        self.assertEqual(profile["records"], 1)
        self.assertEqual(profile["invalid_utf8_rows"], 1)
        self.assertEqual(profile["replacement_character_rows"], 1)
        self.assertIn("\udcfd", rows[0]["description"])
        self.assertEqual(details["invalid_utf8_rows"], [1])
        self.assertEqual(file_hash(path), original)

    def test_reconcile_row_url_hash_and_uncertain_transformation(self):
        raw, clean, matching = self.rows()
        summary, lineage, _, _ = reconcile([raw], [clean], [matching], [])
        self.assertEqual(summary["clean_to_matching"]["verified_description_hashes"], 1)
        self.assertTrue(lineage[0]["raw_primary_url_matches"])
        matching["source_description_sha256"] = "bad"
        clean["source_records_json"] = json.dumps([dict(source_row_number=1, job_url="wrong", site="TEST")])
        summary, _, _, _ = reconcile([raw], [clean], [matching], [])
        self.assertEqual(summary["raw_to_clean"]["invalid_reference_links"], 1)
        self.assertEqual(summary["clean_to_matching"]["mismatched_description_ids"], ["TEST_JOB"])
        self.assertFalse(summary["historical_pipeline_reproduced"])

    def test_spreadsheet_errors_override_false_review_flag(self):
        _, _, matching = self.rows()
        link = dict(clean_matching_hash_verified=True, raw_primary_url_matches=True, raw_links=[dict(url_matches=True, site_matches=True)])
        self.assertEqual(quality(matching, link), [])
        matching["tasks_text"] = "#NAME?"
        reasons = quality(matching, link)
        self.assertIn("spreadsheet_error:tasks_text", reasons)
        self.assertIn("missing_or_short_section:tasks_text", reasons)
        self.assertEqual(matching["needs_review"], "FALSE")

    def test_selection_cues_have_offsets_no_skill_or_month_inference(self):
        _, _, matching = self.rows()
        matching.update(title_for_matching="Data Analyst (Python, SQL)", requirements_text="Cần ít nhất 2 năm phân tích dữ liệu.")
        result = selection_features(matching)
        self.assertEqual(result["role_candidates"], ["Data Analyst"])
        self.assertNotIn("Backend Python", result["role_candidates"])
        for hit in result["experience_mentions"] + result["must_mentions"]:
            self.assertEqual(matching[hit["field"]][hit["start"]:hit["end"]], hit["text"])
        self.assertNotIn("months", result)

    def test_quality_and_multiple_source_keys_propagate_without_false_labels(self):
        spec = dict(kind="jd", namespace="TEST", columns=dict(external_id="id", text="text", related_source_keys="links", quality_reasons="quality"),
                    defaults=dict(text_scope="professional", exposure="prospective"))
        text = "TEST ONLY unique professional requirements for platform systems and data analysis."
        first = record(dict(id="1", text=text, links='["same-url"]', quality='["unverified"]'), spec)
        second = record(dict(id="2", text="Different duties entirely related to testing software and infrastructure.", links='["same-url"]', quality='[]'), spec)
        first["exposure"] = "development"
        groups, _ = group_records([first, second], [])
        self.assertEqual(len(groups), 1)
        self.assertTrue(second["development_only"])
        self.assertEqual(first["decision"], "quarantine")
        self.assertEqual(second["experience"], {})

    def test_selection_excludes_pilot_and_reports_shortage(self):
        _, _, matching = self.rows()
        spec = dict(kind="jd", namespace="TEST", columns=dict(external_id="job_id", text="match_text"),
                    defaults=dict(exposure="prospective", text_scope="professional"))
        row = record(matching, spec)
        row.update(group_id="TEST_GROUP", development_only=True)
        metadata = {"TEST_JOB": selection_features(matching)}
        selected, _ = select_batch([row], metadata)
        self.assertEqual(selected, [])
        row["development_only"] = False
        selected, available = select_batch([row], metadata)
        self.assertEqual(len(selected), 1)
        self.assertEqual(available["Data Analyst"]["records"], 0)
        self.assertEqual(selected[0]["purpose"], "development/parser; not final test")

    def test_end_to_end_preserves_sources_repeats_and_snapshots_context(self):
        raw, clean, matching = self.rows()
        inputs = [self.save(name, [row]) for name, row in zip(("job_descriptions.csv", "jobs_clean.csv", "jobs_matching.csv"), (raw, clean, matching))]
        hashes = {p.name: file_hash(p) for p in inputs}
        first, second = self.folder / "run1", self.folder / "run2"
        result = prepare_upstream(self.folder, first)
        prepare_upstream(self.folder, second)
        self.assertEqual(result["import_summary"]["records"], 1)
        self.assertEqual(result["batch"]["total"], 1)
        self.assertFalse(result["split_locked"])
        self.assertEqual(hashes, {p.name: file_hash(p) for p in inputs})
        for relative in ("canonical_jd.csv", "selection.json", "dataset/records.jsonl", "dataset/groups.json", "summary.json"):
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes())
        verify(first, "upstream")
        context = read_json(first / "dataset/context_sources.json")
        self.assertEqual(len(context), 8)
        self.assertEqual(file_hash(first / "dataset/context/000.csv"), hashes["job_descriptions.csv"])
        self.assertTrue(all(key in matching for key in PROFESSIONAL))
