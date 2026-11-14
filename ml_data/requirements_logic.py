"""Literal requirement clauses and AND/OR evidence; ambiguity is explicit."""
import re


def requirement_logic(row, patterns):
    result = []
    for field in ("requirements_text", "preferred_requirements_text"):
        text = row.get(field, "") or ""
        for match in re.finditer(r"[^\n;]+", text):
            clause = match.group()
            terms = sorted(k for k, (pattern, _) in patterns.items() if re.search(pattern, clause, re.I))
            if not terms:
                continue
            optional = field == "preferred_requirements_text" or bool(re.search(
                r"ưu\s+tiên|không\s+bắt\s+buộc|not\s+required|preferred|optional|nice\s+to", clause, re.I))
            disjunction = bool(re.search(r"\b(?:or|hoặc)\b", clause, re.I))
            conjunction = bool(re.search(r"\b(?:and|và)\b", clause, re.I))
            # Flat multi-term lists and mixed operators cannot be assumed to be AND.
            operator = ("single" if len(terms) == 1 else "mixed_unresolved" if disjunction and conjunction
                        else "any_of" if disjunction else "all_of" if conjunction else "list_unresolved")
            result.append(dict(field=field, start=match.start(), end=match.end(), quote=clause,
                               terms=terms, operator=operator, strength="preferred" if optional else "stated_requirement",
                               use="evidence/diagnostics; not proof that every mentioned term is mandatory"))
    return result
