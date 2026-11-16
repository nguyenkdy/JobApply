"""Intake fixtures, not matching-method tuning on authored holdout CVs."""
from copy import deepcopy

from _support import WorkspaceTest
from ml_data.grouping import group_records
from ml_data.ingest import record
from ml_data.intake import admit_profiles, check_preserved_cv, lexical_diagnostics, occupation_relation, preview


class IntakeTests(WorkspaceTest):
    def fixtures(self):
        design = dict(version="fixture-v1", created_on="2026-11-16", generation_cohort="fixture-author",
            roles=["Role A"], families={k: "Test bank" for k in ("A", "B", "C")}, expected_count=3,
            construction=dict(method="individually_written_full_text", text_assembler=None, shared_template=None,
                grouping_unit="scenario_source_bank", shared_author_is_not_independent_collection=True, minimum_source_banks=3))
        profiles = [dict(id=f"FIX_{bank}", family=bank, role="Role A", kind="unknown",
                        text="Role A\n" + (word + " ")*60 + "\nUsed Python in a fictional fixture; duration unspecified.",
                        skills=["Python"], stack=[], durations=[]) for bank, word in zip(("A", "B", "C"), ("alpha", "beta", "gamma"))]
        return design, profiles

    def records(self, rendered):
        spec = dict(kind="cv", namespace="fixture", columns=dict(external_id="cv_id", text="cv_text", role="role",
            skills="skills", stack="stack", experience="experience_json", source_group="source_group", template_group="template_group",
            exposure="exposure", is_synthetic="is_synthetic", text_scope="text_scope", lineage="lineage_json"))
        return [record(row, spec) for row, _ in rendered]

    def job(self):
        return dict(record_id="J1", group_id="JG", kind="jd", decision="keep", development_only=False,
                    metadata_use_exposure="development", new_jd_holdout_eligible=False,
                    label_policy_status="requires_expanded_taxonomy_policy")

    def test_shared_slot_recipe_rejected_before_bank_count(self):
        design, profiles = self.fixtures()
        for key, value in (("method", "slot_composition"), ("shared_template", "same_template"), ("text_assembler", "render.py")):
            bad = deepcopy(design)
            bad["construction"][key] = value
            with self.assertRaisesRegex(ValueError, "Shared composition"):
                admit_profiles(bad, profiles)
        profiles[0]["blocks"] = ["same", "slots"]
        with self.assertRaisesRegex(ValueError, "slots/recipe"):
            admit_profiles(design, profiles)

    def test_admission_preserves_full_text_and_literal_unknowns(self):
        design, profiles = self.fixtures()
        result = admit_profiles(design, profiles)
        for profile, (row, evidence) in zip(profiles, result):
            self.assertEqual(row["cv_text"], profile["text"])
            self.assertEqual(row["experience_json"], "{}")
            self.assertTrue(evidence["lineage"]["shared_author"])
            self.assertIsNone(evidence["lineage"]["template_family"])
            self.assertEqual(len(evidence["lineage"]["template_ancestors"]), 1)
            for item in evidence["skills"].values():
                self.assertEqual(row["cv_text"][item["start"]:item["end"]], item["quote"])

    def test_relabeling_banks_does_not_erase_common_ancestry(self):
        design, profiles = self.fixtures()
        for p in profiles:
            p["provenance"] = dict(parent_ids=["old_source"], template_ancestors=["one_shared_recipe"])
        records = self.records(admit_profiles(design, profiles))
        groups, edges = group_records(records, [])
        self.assertEqual(len(groups), 1)
        self.assertTrue(any(e["reason"] == "historical_template_lineage" for e in edges))
        assignments, audit = preview(records, [self.job()], groups, [dict(group_id="JG", record_ids=["J1"])],
                                     dict(mode="known-jd", seed=1, seed_retries=0, ratios=[.6, .2, .2]))
        self.assertEqual(len({a["partition"] for a in assignments if a["kind"] == "cv"}), 1)
        self.assertFalse(audit["partition_ready"])

    def test_parent_without_ancestry_and_target_jd_are_rejected(self):
        for provenance, message in ((dict(parent_ids=["old"]), "Variant"), (dict(target_jd_ids=["JD42"]), "Target JD")):
            design, profiles = self.fixtures()
            profiles[0]["provenance"] = provenance
            with self.assertRaisesRegex(ValueError, message):
                admit_profiles(design, profiles)

    def test_source_duplicate_or_false_skill_fails_admission(self):
        design, profiles = self.fixtures()
        bad = deepcopy(profiles)
        bad[1]["text"] = bad[0]["text"]
        with self.assertRaisesRegex(ValueError, "Duplicate authored"):
            admit_profiles(design, bad)
        profiles[0]["skills"] = ["UnmentionedSkill"]
        with self.assertRaisesRegex(ValueError, "Skill absent"):
            admit_profiles(design, profiles)

    def test_development_jd_is_shared_only_with_explicit_guard(self):
        design, profiles = self.fixtures()
        records = self.records(admit_profiles(design, profiles))
        groups, _ = group_records(records, [])
        protocol = dict(mode="known-jd", seed=1, seed_retries=0, ratios=[.6, .2, .2])
        with self.assertRaisesRegex(ValueError, "fixed-seed"):
            preview(records, [self.job()], groups, [], dict(protocol, mode="new-both"))
        with self.assertRaisesRegex(ValueError, "guard missing"):
            preview(records, [dict(self.job(), label_policy_status="")], groups, [], protocol)

    def test_occupation_relationship_does_not_assign_relevance(self):
        for a, b, state in (("Backend Java", "Fullstack", "potentially_overlapping_functions"),
                            ("QA/Testing", "Backend Python", "different_titles_fit_unresolved"),
                            ("Frontend", "", "unknown_or_generic")):
            result = occupation_relation(a, b)
            self.assertEqual(result["state"], state)
            self.assertIsNone(result["relevance"])
            self.assertFalse(result["can_infer_negative"])

    def test_lexical_check_is_not_independence_certificate(self):
        records = [dict(record_id="A", text_normalized="same sentence in both sources", template_group="X"),
                   dict(record_id="B", text_normalized="same sentence in both sources", template_group="Y")]
        result = lexical_diagnostics(records, [])
        self.assertEqual(result["maximum_cross_bank_jaccard"], 1)
        self.assertFalse(result["semantic_independence_established"])
        self.assertFalse(result["deleted_v5_text_comparison_performed"])

    def test_prior_identity_cannot_be_renamespaced_or_reworded(self):
        design, profiles = self.fixtures()
        old = self.records(admit_profiles(design, profiles))
        check_preserved_cv(old, deepcopy(old))
        for key, value in (("namespace", "new"), ("template_group", "renamed"), ("text_original", "rewritten"), ("exposure", "development")):
            altered = deepcopy(old)
            altered[0][key] = value
            with self.assertRaisesRegex(ValueError, "identity/lineage"):
                check_preserved_cv(old, altered)

    def test_pinned_prior_partitions_survive_new_banks(self):
        design, profiles = self.fixtures()
        records = self.records(admit_profiles(design, profiles))
        groups, _ = group_records(records, [])
        protocol = dict(mode="known-jd", seed=20261116, seed_retries=0, ratios=[.6, .2, .2])
        old, _ = preview(records, [self.job()], groups, [], protocol)
        other = deepcopy(records[0])
        other.update(record_id="new", group_id="new-group", template_group="new-bank", source_group="new-source",
                     text_normalized="completely separate source")
        # Use a completed grouping result: test preservation and leakage policy,
        # not a new text-similarity algorithm.
        assignments, audit = preview(records + [other], [self.job()], groups + [dict(group_id="new-group", kind="cv", record_ids=["new"], development_only=False)], [], protocol, old)
        self.assertTrue(audit["leakage_check_passed"])
        actual = {a["record_id"]: a["partition"] for a in assignments}
        for a in old:
            self.assertEqual(actual[a["record_id"]], a["partition"])
        prior_dev = deepcopy(old)
        next(a for a in prior_dev if a["kind"] == "cv")["partition"] = "development"
        with self.assertRaisesRegex(ValueError, "cannot become prospective"):
            preview(records, [self.job()], groups, [], protocol, prior_dev)
