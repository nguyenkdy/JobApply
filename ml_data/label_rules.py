"""Conservative automatic proxy labels. No claim of human or independent gold."""

ROLE_SCOPES = {
    "backend python": {"backend python", "python backend"},
    "backend java": {"backend java", "java backend"},
    "frontend": {"frontend"},
    "devops/cloud": {"devops"},
    "qa/testing": {"kiểm thử phần mềm", "software testing"},
    "data analyst": {"data analysis"},
}


def experience_coverage(cv, jd, receipt=None):
    """Match exact documented scopes; every extracted bound must be covered.

    Generic professional/software months are accepted only if explicitly
    asserted by the CV source. They never supply technology-specific months.
    """
    if cv.get("lineage", {}).get("experience_kind") not in {"employment", "contract"}:
        return "incomparable"
    required = jd.get("experience", {})
    if not required:
        return "unknown"
    observed = cv.get("experience", {})
    missing, below = [], []
    for scope, need in required.items():
        aliases = next((values for values in ROLE_SCOPES.values() if scope in values), {scope})
        values = [observed[s] for s in aliases if s in observed]
        if not values:
            missing.append(scope)
            continue
        # Strictness belongs to the controlling bound, not another smaller bound.
        strict = any(e.get("strictly_greater") and e.get("threshold_months") == need
                     and set(e.get("scopes", [])) & aliases
                     for e in (receipt or {}).get("experience_evidence", []))
        if max(values) < need or (strict and max(values) == need):
            below.append(scope)
    return "below" if below else "unknown" if missing else "satisfied"


def label_pair_row(pair_row, cv_rec, jd_rec, jd_receipt=None):
    role, target = cv_rec.get("role", "").casefold(), jd_rec.get("role", "").casefold()
    skills = set(cv_rec.get("skills", [])) & set(jd_rec.get("skills", []))
    stack = set(cv_rec.get("stack", [])) & set(jd_rec.get("stack", []))
    duration_state = experience_coverage(cv_rec, jd_rec, jd_receipt)
    status, label = "labeled", ""
    if not role or not target:
        status, reason = "insufficient_evidence", "Role is unknown or ambiguous; not evidence of irrelevance."
    elif role != target:
        label, reason = "0", "Different explicit primary roles under this proxy rubric; shared keywords alone are insufficient."
    elif not cv_rec.get("skills") or not jd_rec.get("skills"):
        status, reason = "insufficient_evidence", "Same role but a source has no explicit skill metadata."
    elif not skills and not stack:
        label, reason = "1", "Explicit primary role agrees; observed technology sets differ. This is only role-level proxy compatibility, not demonstrated technical fit."
    elif duration_state in {"unknown", "incomparable"}:
        label, reason = "1", "Same role with shared technology; professional duration is unknown or incomparable (including project/internship)."
    elif duration_state == "satisfied" and stack:
        label, reason = "2", "Same role, shared stack and comparable role duration meets the extracted bound under the proxy rubric."
    else:
        label, reason = "1", "Same role and some shared technology, but stack or comparable duration does not establish full proxy fit."
    reason += " Automatic rule label, not verified suitability."
    # Full professional text contains every asserted premise; short generic prefixes
    # previously missed skill/experience evidence used in the rationale.
    return dict(pair_row, label_status=status, relevance_0_1_2=label,
                cv_evidence=pair_row["cv_text"], jd_evidence=pair_row["jd_text"], rationale=reason)
