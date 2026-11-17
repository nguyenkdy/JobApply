"""Bounded syntax extensions, retaining evidence and all unconsumed conditions."""
from copy import deepcopy
import re

from ml_data import technical_policy_v2 as v2

VERSION = "expanded-technical-proxy-v3"
POLICY = dict(v2.POLICY, version=VERSION,
    changes="Full-match duration variants; single-predicate terminal preference; guarded sentence decomposition; complete technical prefixes",
    residual_policy="Unconsumed residual remains unresolved and blocks label 2; no title-derived duration scope",
    parent="expanded-technical-proxy-v2", model_training=False)

TIME = r"(?:(?:at least|minimum(?: of)?|more than|over|tối thiểu|ít nhất|từ|trên)\s+)?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?\s*\+?\s*(?:years?|months?|năm|tháng)(?:\s+trở lên)?"
PREFERENCE_END = re.compile(r"\s+(?:is (?:a plus|an advantage|preferred|advantageous)|là (?:một |1 )?lợi thế(?: lớn)?)$", re.I)
NEW_PREFIX = re.compile(r"^(?:familiarity with|knowledge and experience (?:in|with)|experience (?:in )?using|"
    r"proficiency in using|strong proficiency in|good knowledge of|"
    r"có kiến thức (?:về|với)|có hiểu biết (?:về|với)|nắm vững|sử dụng tốt)\s+", re.I)


def clean(text):
    value = v2.clean(text).lstrip("●・–+ ")
    # Numbered bullet, not a decimal year value such as 1.5 years.
    return re.sub(r"^\d+[.)]\s+", "", value)


def duration(text):
    value = clean(text)
    found = v2.parse_duration(value)
    if found:
        return found
    if (v2.OPTIONAL.search(value) or v2.CONDITION.search(value) or
            re.search(r"\b(?:no|not|without|never)\b|không|chưa|~|tương đương|similar|relevant", value, re.I)):
        return None
    value = re.sub(r"^(?:you (?:must )?have|must have|have|has)\s+", "", value, flags=re.I)
    # Scope-first and generic trailing-duration clauses must match the whole sentence.
    m = re.fullmatch(r"(?:có )?kinh nghiệm(?: làm việc)?\s+(?P<time>" + TIME + r")", value, re.I)
    if m:
        value = m["time"] + " kinh nghiệm làm việc"
    else:
        value = re.sub(r"^(?:có )?kinh nghiệm\s+(?=" + TIME + r")", "", value, flags=re.I)
        value = re.sub(r"^có\s+", "", value, flags=re.I)
    m = re.fullmatch(r"(?P<time>" + TIME + r")\s+(?P<body>.+)", value, re.I)
    if not m:
        return None
    body = m["body"].casefold()
    body = re.sub(r"^of\s+", "", body)
    exact = {
        "software development experience": "software development",
        "working as developers": "software development",
        "working experience in software development": "software development",
        "professional experience in software development": "software development",
        "kinh nghiệm về phát triển phần mềm": "phát triển phần mềm",
        "kinh nghiệm làm việc trong lĩnh vực phát triển phần mềm": "phát triển phần mềm",
        "làm việc trong lĩnh vực phát triển phần mềm": "phát triển phần mềm",
        "kinh nghiệm làm việc với vai trò backend developer": "backend",
        "kinh nghiệm làm back-end developer": "backend",
        "kinh nghiệm trong lĩnh vực phát triển phần mềm ở vị trí backend": "backend",
        "kinh nghiệm trong lĩnh vực phát triển sản phẩm ở vị trí backend": "backend",
        "kinh nghiệm làm về backend": "backend",
        "experience in software testing (web and mobile)": "kiểm thử phần mềm",
    }
    if body in exact:
        body = exact[body]
    else:
        # Only one fully consumed technology; combined skills never inherit duration.
        body = re.sub(r"^(?:(?:professional |working |hands-on )?experience (?:in|with)|kinh nghiệm(?: trở lên)? (?:lập trình (?:với|trên)|phát triển phần mềm với công nghệ|trong phát triển|sử dụng tốt))\s+", "", body)
        body = re.sub(r"\s+(?:development(?: experience)?|language)$", "", body)
        body = re.sub(r"^professional\s+", "", body)
        hits = v2.mentions(body)
        if len(hits) == 1 and hits[0][0] == 0 and hits[0][1] == len(body):
            body = "experience with " + hits[0][2]
    result = v2.parse_duration(m["time"] + " " + body)
    if result:
        result["normalization"] = "explicit-duration-scope-v3"
    return result


def terminal_preference(text):
    """Accept one predicate qualified as a whole; reject local or compound preferences."""
    value = clean(text)
    match = PREFERENCE_END.search(value)
    if not match:
        return False
    body = value[:match.start()]
    if re.search(r"\bmust\b|required|bắt buộc|yêu cầu|[,;()]|\.(?:\s|$)", body, re.I):
        return False
    prefix = v2.PREFIX.match(body) or NEW_PREFIX.match(body)
    if not prefix:
        return False
    remainder = body[prefix.end():]
    return not bool(v2.PREFIX.search(remainder) or re.search(r"\b(?:experience|knowledge)\b|kinh nghiệm|thành thạo", remainder, re.I))


def parse(text, field="requirements_text"):
    value = clean(text)
    base = v2.parse_technical(value, field)
    if field.startswith("preferred"):
        return base
    if terminal_preference(value):
        return dict(base, state="preferred", reason="whole_predicate_terminal_preference")
    if base["state"] != "unresolved" or base["reason"] == "conditional_applicability":
        return base
    parsed = duration(value)
    if parsed:
        return dict(base, state="duration", reason="complete_duration_variant", duration=parsed)
    prefix = NEW_PREFIX.match(value)
    if prefix and not v2.optional_state(value) and not v2.NUMERIC_TIME.search(value):
        tree = v2.logic_tree(value[prefix.end():])
        if tree:
            return dict(base, state="mandatory", tree=tree, reason="complete_technical_prefix_variant")
    return base


def revise_clause(clause):
    """Do not loosen inherited conditional/preferred section applicability."""
    if clause["state"] != "unresolved" or clause["reason"] == "conditional_applicability":
        return [deepcopy(clause)]
    span = clause["evidence"]
    quote = span["quote"]
    parsed = parse(quote, span["field"])
    if parsed["state"] != "unresolved":
        return [dict(parsed, evidence=deepcopy(span))]
    # Split explicit sentence boundaries, never Node.js/.NET or decimal values.
    # Alternatives and references can span sentences; leave those clauses untouched.
    if re.search(r"\b(?:either|or|otherwise|instead|alternatively|unless)\b|một trong|hoặc|thay thế|nếu", quote, re.I):
        return [deepcopy(clause)]
    if re.search(r"\.\s+(?:this|that|these|those|it|however|not required|optional|điều này|yêu cầu này|không bắt buộc)\b", quote, re.I):
        return [deepcopy(clause)]
    parts = list(re.finditer(r".+?(?:\.(?=\s+[A-ZÀ-ỸĐ])|$)", quote))
    if len(parts) < 2:
        return [deepcopy(clause)]
    result = []
    for part in parts:
        item = parse(part[0], span["field"])
        # Do not erase unknown nontechnical fragments from an unresolved parent.
        if item["state"] == "outside_technical_grammar":
            item = dict(item, state="unresolved", reason="unconsumed_sentence_residual")
        result.append(dict(item, evidence=dict(field=span["field"], start=span["start"]+part.start(),
            end=span["start"]+part.end(), quote=part[0])))
    return result


def jd_facts(original):
    result = deepcopy(original)
    result["version"] = VERSION
    result["clauses"] = [dict(c, parent_clause_index=index) for index, old in enumerate(original["clauses"]) for c in revise_clause(old)]
    preferred = [c["evidence"] for c in result["clauses"] if c["state"] == "preferred"]
    # Never use a newly recognized preference as affirmative core-skill evidence.
    result["skills"] = {k: s for k, s in original["skills"].items() if not any(
        p["field"] == s["field"] and p["start"] <= s["start"] < s["end"] <= p["end"] for p in preferred)}
    return result


judge = v2.judge
