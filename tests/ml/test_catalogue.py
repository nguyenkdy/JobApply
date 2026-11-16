"""Full-catalogue safeguards: no silent filtering, exposure reset or invented metadata."""
from copy import deepcopy

from _support import WorkspaceTest
from ml_data.catalogue import audit_evidence, catalogue_views, coverage_plan


class CatalogueTests(WorkspaceTest):
    def row(self, i, **updates):
        result = dict(kind="jd", record_id=f"J{i}", external_id=f"job{i}", group_id=f"G{i}",
                      decision="keep", decision_reasons=[], development_only=False, exposure="prospective",
                      role="backend python", skills=["python"], stack=["django"], experience={"python": 12})
        result.update(updates)
        return result

    def test_all_eligible_roles_and_unknowns_survive_without_mutation(self):
        rows = [self.row(1), self.row(2, role="game developer"), self.row(3, role="", skills=[], stack=[], experience={}),
                self.row(4, development_only=True, exposure="development"),
                self.row(5, decision="quarantine", decision_reasons=["spreadsheet_error"]),
                self.row(6, decision="exclude_exact_duplicate")]
        before = deepcopy(rows)
        selected, audit, groups = catalogue_views(rows, {"J1"})
        self.assertEqual([r["record_id"] for r in selected], ["J1", "J2", "J3"])
        self.assertEqual(rows, before)
        self.assertEqual(len(groups), 3)
        self.assertEqual(audit[2]["metadata_flags"], ["role_unknown", "skills_unknown", "stack_unknown", "experience_unknown"])
        self.assertEqual([r["disposition"] for r in audit[3:]], ["development_only", "quarantine", "exclude_exact_duplicate"])

    def test_near_group_members_retained_and_observed_group_propagates(self):
        rows = [self.row(1), self.row(2, group_id="G1"), self.row(3)]
        selected, audit, groups = catalogue_views(rows, {"J1"})
        self.assertEqual(len(selected), 3)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["record_ids"], ["J1", "J2"])
        self.assertEqual(audit[1]["benchmark_exposure"], "same_group_as_completed_benchmark")
        self.assertIn("multiple_candidate_records_in_group", audit[1]["metadata_flags"])

    def test_duplicate_ids_ineligible_old_catalogue_and_development_leak_fail(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            catalogue_views([self.row(1), self.row(1)], set())
        with self.assertRaisesRegex(ValueError, "ineligible"):
            catalogue_views([self.row(1, development_only=True)], {"J1"})
        with self.assertRaisesRegex(ValueError, "Development"):
            catalogue_views([self.row(1, development_only=True), self.row(2, group_id="G1")], set())

    def test_forecast_counts_unknowns_and_uncovered_roles_without_assigning_labels(self):
        cvs = [dict(role="backend python", skills=["python"]), dict(role="backend java", skills=["java"])]
        jobs = [self.row(1, role=""), self.row(2, skills=[]), self.row(3, role="game developer")]
        plan = coverage_plan(jobs, cvs)
        self.assertEqual(plan["full_grid_pairs"], 6)
        self.assertEqual(plan["pairs_missing_minimum_proxy_metadata"], 3)
        self.assertEqual(next(r for r in plan["by_role"] if r["role"] == "game developer")["existing_cv_count"], 0)
        self.assertTrue(all("relevance_0_1_2" not in j for j in jobs))

    def test_evidence_checks_source_offsets_and_metadata_consistency(self):
        source = dict(job_id="job1", requirements_text="Python", extracted_role="", extracted_skills="python",
                      extracted_stack="", extracted_experience_json="{}")
        receipt = dict(job_id="job1", role="", skills=["python"], stack=[], experience={}, extractor_version="TEST",
                       role_evidence=[], experience_evidence=[], requirement_clauses=[], stack_evidence={}, preferred_skill_evidence={},
                       skill_evidence={"python": dict(field="requirements_text", start=0, end=6, quote="Python")})
        self.assertEqual(audit_evidence([source], [receipt])["literal_spans_verified"], 1)
        bad = deepcopy(receipt)
        bad["skill_evidence"]["python"]["quote"] = "Java"
        with self.assertRaisesRegex(ValueError, "span"):
            audit_evidence([source], [bad])
        with self.assertRaisesRegex(ValueError, "Metadata"):
            audit_evidence([dict(source, extracted_experience_json='{"python": 24}')], [receipt])
