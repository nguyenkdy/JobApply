"""Prerequisites only: ancestry, corpus grids, evidence and proxy target semantics."""
from collections import Counter
from copy import deepcopy
import json

from _support import ROOT, WorkspaceTest
from ml_data.annotation import label_pairs_by_evidence
from ml_data.cohort import export_cohort
from ml_data.common import csv_rows, file_hash, read_json, read_lines, write_csv, write_json
from ml_data.expansion import CV_COLUMNS
from ml_data.ingest import ingest
from ml_data.label_rules import experience_coverage, label_pair_row
from ml_data.pretraining import check_conditions
from ml_data.requirements_logic import requirement_logic
from ml_data.sampling import sample_pairs
from ml_data.splitting import make_split
from ml_data.synthetic import render_batch


class PretrainingTests(WorkspaceTest):
    def test_new_cohort_preserves_design_and_literal_evidence_reproducibly(self):
        assets = ROOT / "ml_data_assets/independent_cv_v3"
        a, b = self.folder / "a", self.folder / "b"
        summary = export_cohort(assets, a)
        export_cohort(assets, b)
        self.assertEqual(file_hash(a / "manifest.json"), file_hash(b / "manifest.json"))
        self.assertEqual(summary["template_groups"], 12)
        self.assertEqual(summary["experience_kinds"], {k: 12 for k in ("employment", "project", "internship", "contract", "unknown")})
        rows = {r["cv_id"]: r for r in csv_rows(a / "cvs.csv")[1]}
        for item in read_json(a / "evidence.json"):
            row = rows[item["cv_id"]]
            self.assertEqual(item["lineage"]["parent_ids"], [])
            for evidence in [*item["skills"].values(), *item["durations"]]:
                self.assertEqual(row["cv_text"][evidence["start"]:evidence["end"]], evidence["quote"])
            if item["lineage"]["experience_kind"] == "unknown":
                self.assertEqual(json.loads(row["experience_json"]), {})

    def test_scope_coverage_requires_each_bound_and_correct_strictness(self):
        cv = dict(experience={"professional experience": 60, "python": 24}, lineage={"experience_kind": "employment"})
        jd = dict(experience={"professional experience": 36, "python": 36})
        self.assertEqual(experience_coverage(cv, jd), "below")
        jd["experience"] = {"professional experience": 60}
        smaller_strict = dict(experience_evidence=[dict(scopes=["professional experience"], threshold_months=24, strictly_greater=True)])
        self.assertEqual(experience_coverage(cv, jd, smaller_strict), "satisfied")
        jd["experience"] = {"django": 6}
        self.assertEqual(experience_coverage(cv, jd), "unknown")
        cv["lineage"]["experience_kind"] = "project"
        self.assertEqual(experience_coverage(cv, jd), "incomparable")

    def test_known_different_skills_are_distinct_from_missing_metadata(self):
        cv = dict(role="frontend", skills=["vue"], stack=["vue"], experience={})
        jd = dict(role="frontend", skills=["react"], stack=["react"], experience={})
        pair = dict(cv_text="TEST ONLY Vue frontend", jd_text="TEST ONLY React frontend")
        self.assertEqual(label_pair_row(pair, cv, jd)["relevance_0_1_2"], "1")
        jd["skills"] = []
        self.assertEqual(label_pair_row(pair, cv, jd)["label_status"], "insufficient_evidence")
        jd["role"] = ""
        self.assertEqual(label_pair_row(pair, cv, jd)["relevance_0_1_2"], "")

    def test_and_or_optional_and_ambiguous_logic_retains_spans(self):
        row = dict(requirements_text="Python or Java\nPython and SQL\nPython or Java and SQL\nPython, Java\nOptional SQL", preferred_requirements_text="Python")
        patterns = {s: (rf"\b{s}\b", True) for s in ("python", "java", "sql")}
        clauses = requirement_logic(row, patterns)
        self.assertEqual([c["operator"] for c in clauses[:4]], ["any_of", "all_of", "mixed_unresolved", "list_unresolved"])
        self.assertEqual(clauses[-1]["strength"], "preferred")
        self.assertEqual(clauses[-2]["strength"], "preferred")
        for c in clauses:
            self.assertEqual(row[c["field"]][c["start"]:c["end"]], c["quote"])

    def test_complete_prerequisites_and_semantically_incomplete_grid_rejected(self):
        # TEST ONLY JD fixture. No model scores or target-JD-based CV authoring.
        export_cohort(ROOT / "ml_data_assets/independent_cv_v3", self.folder / "new")
        # V1 is still a supported renderer/regression source. V2 authoring assets
        # are retired; this fixture only needs sixty protected development CVs.
        render_batch(ROOT / "ml_data_assets/synthetic_cv_v1", self.folder / "old")
        columns, old = csv_rows(self.folder / "old/cvs.csv")
        for row in old:
            row["exposure"] = "development"
        write_csv(self.folder / "old_development.csv", old, columns)
        roles = ["Backend Python", "Backend Java", "Frontend", "DevOps/Cloud", "QA/Testing"]
        jobs = [dict(id=f"TEST_JOB_{i}", text="TEST ONLY " + " ".join(f"unique{i}word{k}" for k in range(30)),
                     role=roles[i % 5], skills="python;java;sql;linux;react", stack="django;spring boot;react;terraform;selenium",
                     experience='{"professional experience": 12}') for i in range(50)]
        write_csv(self.folder / "jobs.csv", jobs, tuple(jobs[0]))
        sources = [dict(kind="jd", path="jobs.csv", namespace="TEST_JD", version="1",
            columns=dict(external_id="id", text="text", role="role", skills="skills", stack="stack", experience="experience"),
            defaults=dict(exposure="prospective", text_scope="professional"))]
        for path, namespace in (("new/cvs.csv", "independent-careers-v3"), ("old_development.csv", "jobapply-synthetic-careers-v2")):
            sources.append(dict(kind="cv", path=path, namespace=namespace, version="1", columns=CV_COLUMNS))
        write_json(self.folder / "config.json", dict(schema_version=1, dataset_version="TEST_ONLY", sources=sources))
        ingest(self.folder / "config.json", self.folder / "dataset")
        make_split(self.folder / "dataset", self.folder / "split", eval_jd_per_role=10)
        for p in ("train", "validation", "test"):
            sample_pairs(self.folder / "dataset", self.folder / "split", self.folder / (p + "_pairs"), partition=p,
                         strategy="census", evaluation_catalogue_only=True)
            label_pairs_by_evidence(self.folder / "dataset", self.folder / (p + "_pairs"), output=self.folder / (p + "_labels"))
        ready = check_conditions(self.folder, sealed=False)
        self.assertTrue(ready["ready_for_automatic_label_experiment"], ready["blockers"])
        self.assertEqual(ready["pair_counts"], dict(train=1500, validation=750, test=750))
        assignments = read_lines(self.folder / "split/assignments.jsonl")
        self.assertEqual(Counter(a["partition"] for a in assignments if a["kind"] == "cv"),
                         dict(development=60, train=30, validation=15, test=15))
        # A self-consistent hash is insufficient: alter both input and output to
        # repeat one CV/JD combination while keeping distinct pair IDs and row count.
        pdir, ldir = self.folder / "test_pairs", self.folder / "test_labels"
        columns, rows = csv_rows(pdir / "pairs.csv")
        _, labeled = csv_rows(ldir / "pairs.csv")
        replacement = deepcopy(rows[1])
        replacement["pair_id"] = rows[0]["pair_id"]
        rows[0] = replacement
        replacement_label = deepcopy(labeled[1])
        replacement_label["pair_id"] = labeled[0]["pair_id"]
        labeled[0] = replacement_label
        for directory, changed in ((pdir, rows), (ldir, labeled)):
            (directory / "pairs.csv").unlink()
            write_csv(directory / "pairs.csv", changed, columns)
            manifest = read_json(directory / "manifest.json")
            manifest["artifacts"]["pairs.csv"] = file_hash(directory / "pairs.csv")
            if directory == ldir:
                manifest["source_pairs_manifest_sha256"] = file_hash(pdir / "manifest.json")
            (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        ready = check_conditions(self.folder, sealed=False)
        self.assertFalse(ready["ready_for_automatic_label_experiment"])
        self.assertIn("test_full_catalogue_grid", ready["blockers"])
