"""Export independently authored profiles; exact metadata assertions, no JD input."""
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from .common import digest, file_hash, fresh_folder, read_json, require, seal, write_csv, write_json
from .synthetic import FIELDS

SCOPE_PHRASES = {"professional experience": "kinh nghiệm nghề nghiệp", "software development": "phát triển phần mềm"}


def render_profile(profile, design):
    require(profile["family"] in design["families"], "Unknown actual writing family")
    require(profile["role"] in design["roles"], "Unknown role")
    require(profile["kind"] in {"employment", "project", "internship", "contract", "unknown"}, "Unknown experience kind")
    text = profile["text"]
    require(len(text) >= 250 and profile["role"].casefold() in text.casefold(), "Professional role/text evidence missing")

    def locate(quote):
        require(quote and quote in text, "Authored evidence is not a literal substring")
        offset = text.index(quote)
        return dict(quote=quote, start=offset, end=offset + len(quote))

    skills = {}
    declared_skills = profile["skills"]
    if isinstance(declared_skills, list):
        # Terms are selected by the scenario author, not extracted from JD/ranking.
        declared_skills = {term: max((line for line in text.splitlines()[1:]
                           if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", line, re.I)), key=len, default="")
                           for term in declared_skills}
    for term, quote in declared_skills.items():
        require(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", quote, re.I), "Skill absent from its evidence")
        skills[term] = locate(quote)
    require(set(profile["stack"]) <= set(skills), "Stack lacks evidence")
    months, durations = {}, []
    for item in profile["durations"]:
        require(type(item["months"]) is int and item["months"] > 0, "Unknown duration must be omitted")
        require(item["scope"] not in months, "Duplicate scoped duration")
        require(re.search(r"(?<!\d)" + str(item["months"]) + r" tháng(?!\w)", item["quote"]), "Month evidence mismatch")
        phrase = SCOPE_PHRASES.get(item["scope"], item["scope"])
        require(phrase.casefold() in item["quote"].casefold(), "Explicit scope phrase missing")
        months[item["scope"]] = item["months"]
        durations.append(dict(scope=item["scope"], scope_phrase=phrase, normalization="explicit-scope-alias-v1",
                              months=item["months"], kind=profile["kind"], **locate(item["quote"])))
    require(profile["kind"] != "unknown" or not months, "Unknown timeline cannot have invented months")
    lineage = dict(scenario_id=profile["id"], generation_version=design["version"],
        generation_cohort=design["generation_cohort"], template_family=profile["family"],
        experience_kind=profile["kind"], parent_ids=[], template_ancestors=[],
        method="new individually authored scenario; no target JD/ranking/label; shared family framework",
        variant_history=[dict(version=1, date=design["created_on"], action="new source scenario")])
    row = dict(cv_id=profile["id"], cv_text=text, role=profile["role"],
        source_group="independent-source:" + profile["id"], template_group=design["version"] + ":" + profile["family"],
        skills=";".join(skills), stack=";".join(profile["stack"]), is_synthetic="true", exposure="prospective",
        text_scope="professional", experience_json=json.dumps(months, ensure_ascii=False, sort_keys=True),
        lineage_json=json.dumps(lineage, ensure_ascii=False, sort_keys=True))
    return row, dict(cv_id=profile["id"], text_sha256=digest(text), skills=skills, durations=durations,
                     lineage=lineage, status="synthetic_author_assertions_not_gold")


def export_cohort(assets, output):
    assets = Path(assets).resolve()
    design, profiles = read_json(assets / "design.json"), read_json(assets / "profiles.json")
    require(len(profiles) == design["expected_count"] == len({p["id"] for p in profiles}), "Wrong count or duplicate IDs")
    require(Counter(p["role"] for p in profiles) == {r: 12 for r in design["roles"]}, "Role distribution differs from prior design")
    for family in design["families"]:
        siblings = [p for p in profiles if p["family"] == family]
        require(len(siblings) == 5 and {p["role"] for p in siblings} == set(design["roles"]), "Family must contain five planned roles")
        require({p["kind"] for p in siblings} == {"employment", "project", "internship", "contract", "unknown"}, "Family experience design changed")
    rendered = [render_profile(p, design) for p in profiles]
    folder = fresh_folder(output, (assets,))
    for name in ("design.json", "profiles.json"):
        shutil.copyfile(assets / name, folder / name)
    write_csv(folder / "cvs.csv", [r for r, _ in rendered], FIELDS)
    write_json(folder / "evidence.json", [e for _, e in rendered])
    summary = dict(cv_count=len(profiles), source_groups=len(profiles), template_groups=len(design["families"]),
        roles=dict(Counter(p["role"] for p in profiles)), experience_kinds=dict(Counter(p["kind"] for p in profiles)),
        is_synthetic=True, labels_created=0, shared_author_cohort=True)
    write_json(folder / "summary.json", summary)
    seal(folder, "synthetic-cvs", dict(generation_version=design["version"], design_sha256=file_hash(assets / "design.json")))
    return summary
