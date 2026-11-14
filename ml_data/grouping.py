"""Conservative source/template/exact/lexical-near grouping, independent of labels."""
from collections import Counter, defaultdict
import math
import re

from .common import digest, require

TOKEN = re.compile(r"\w+(?:[+#.\-]+\w*)*", re.UNICODE)


def shingles(text):
    words = TOKEN.findall(text.casefold())
    if len(words) < 3:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i+3]) for i in range(len(words)-2)}


def near_pairs(rows, threshold):
    """Exact threshold search on 3-token shingle Jaccard with prefix filtering.

    A common rare-first ordering gives a shared prefix for every pair above
    threshold. This avoids comparing every long document pair; not semantic NLP.
    """
    require(type(threshold) in (int, float) and 0 < threshold <= 1, "near_threshold must be in (0,1]")
    sets = {r["record_id"]: shingles(r["text_normalized"]) for r in rows}
    frequency = Counter(s for values in sets.values() for s in values)
    index = defaultdict(set)
    for rid in sorted(sets, key=lambda key: (len(sets[key]), key)):
        values = sets[rid]
        if not values:
            continue
        ordered = sorted(values, key=lambda s: (frequency[s], s))
        prefix = ordered[:len(values) - math.ceil(threshold * len(values)) + 1]
        candidates = set().union(*(index[s] for s in prefix))
        for other in sorted(candidates):
            previous = sets[other]
            if len(previous) < threshold * len(values):
                continue
            intersection = len(values & previous)
            score = intersection / (len(values) + len(previous) - intersection)
            if score >= threshold:
                yield other, rid, score
        for token in prefix:
            index[token].add(rid)


def group_records(records, anchors, threshold=0.85):
    all_rows = records + anchors
    by_id = {r["record_id"]: r for r in all_rows}
    require(len(by_id) == len(all_rows), "Duplicate internal record IDs")
    parent = {rid: rid for rid in by_id}
    edges = []

    def find(rid):
        while parent[rid] != rid:
            parent[rid] = parent[parent[rid]]
            rid = parent[rid]
        return rid

    def link(left, right, reason, score=None):
        a, b = find(left), find(right)
        parent[max(a, b)] = min(a, b)
        edges.append(dict(left=left, right=right, reason=reason, similarity=score))

    for kind in ("cv", "jd"):
        rows = sorted((r for r in all_rows if r["kind"] == kind), key=lambda r: r["record_id"])
        for field in ("entity_id", "source_group", "template_group", "normalized_sha256"):
            buckets = defaultdict(list)
            for row in rows:
                if row.get(field):
                    buckets[row[field]].append(row["record_id"])
            for ids in buckets.values():
                for rid in ids[1:]:
                    link(ids[0], rid, field)
        related = defaultdict(list)
        # A layout revision never erases earlier shared template ancestry.
        templates = defaultdict(list)
        for row in rows:
            for key in set(row.get("lineage", {}).get("template_ancestors", [])):
                templates[key].append(row["record_id"])
            if row.get("template_group"):
                templates[row["template_group"]].append(row["record_id"])
        for ids in templates.values():
            ids = sorted(set(ids))
            for rid in ids[1:]:
                link(ids[0], rid, "historical_template_lineage")
        for row in rows:
            for key in set(row.get("related_source_keys", [])):
                related[key].append(row["record_id"])
        for ids in related.values():
            for rid in ids[1:]:
                link(ids[0], rid, "related_source_key")
        pilot_ids = {r["external_id"]: r["record_id"] for r in anchors if r["kind"] == kind}
        pilot_hashes = {h: r["record_id"] for r in anchors if r["kind"] == kind
                        for h in (r["text_sha256"], r.get("upstream_text_sha256")) if h}
        for row in rows:
            if row.get("protected_pilot"):
                continue
            if row["external_id"] in pilot_ids:
                link(row["record_id"], pilot_ids[row["external_id"]], "pilot_source_id")
            for h in (row["text_sha256"], row.get("upstream_text_sha256")):
                if h and h in pilot_hashes:
                    link(row["record_id"], pilot_hashes[h], "pilot_source_text_hash")
        # Exact duplicates need only one lexical representative; already connected.
        representatives = {}
        for row in rows:
            representatives.setdefault(row["normalized_sha256"], row)
        for left, right, score in near_pairs(list(representatives.values()), threshold):
            link(left, right, "near_3token_jaccard", score)
    members = defaultdict(list)
    for rid in sorted(by_id):
        members[find(rid)].append(rid)
    groups = []
    for ids in sorted(members.values()):
        group_id = "G_" + digest("|".join(ids))[:24]
        exposed = any(by_id[r].get("protected_pilot") or by_id[r]["exposure"] == "development" for r in ids)
        real_ids = [rid for rid in ids if not by_id[rid].get("protected_pilot")]
        if not real_ids:
            continue
        groups.append(dict(group_id=group_id, kind=by_id[ids[0]]["kind"], record_ids=real_ids,
                           protected_pilot_ids=[rid for rid in ids if by_id[rid].get("protected_pilot")], development_only=exposed))
        for rid in real_ids:
            by_id[rid]["group_id"] = group_id
            by_id[rid]["development_only"] = exposed
    # Only exact normalized copies are excluded, never near duplicates automatically.
    exact = defaultdict(list)
    for row in records:
        if row["decision"] == "keep":
            exact[row["kind"], row["normalized_sha256"]].append(row)
    for copies in exact.values():
        copies.sort(key=lambda r: r["record_id"])
        for row in copies[1:]:
            row["decision"] = "exclude_exact_duplicate"
            row["decision_reasons"].append("same_normalized_text_as:" + copies[0]["record_id"])
    for row in records:
        if row["decision"] == "keep":
            row["decision_reasons"].append("retained; near/source/template relatives grouped, not deleted")
    return sorted(groups, key=lambda g: g["group_id"]), edges
