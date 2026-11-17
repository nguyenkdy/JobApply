"""Authored development assertions; neither independent gold nor CV/JD relevance labels."""
import json
from .contract import source_hash


def cases():
    rows = [
        ("duration_vi", "requirements_text", "Có ít nhất 3 năm kinh nghiệm với Python.", "experience", {"scope": "python", "minimum_months": 36, "operator": "minimum"}, "required", True),
        ("duration_strict", "requirements_text", "Over 2 years of experience with Java.", "experience", {"scope": "java", "minimum_months": 24, "operator": "strict_minimum"}, "required", True),
        ("duration_range", "requirements_text", "Minimum 2-3 years of experience in JavaScript development.", "experience", {"scope": "javascript", "minimum_months": 24, "maximum_months": 36, "operator": "range"}, "required", True),
        ("duration_decimal", "requirements_text", "1.5 years of experience with Python", "experience", {"minimum_months": 18}, "required", True),
        ("generic_time", "requirements_text", "Kinh nghiệm từ 2 năm trở lên", "experience", {"scope": "professional experience", "minimum_months": 24}, "required", True),
        ("ambiguous_scope", "requirements_text", "3 năm ở vị trí tương tự", "experience", {}, "required", False),
        ("preferred_time", "preferred_requirements_text", "3 years of experience with Python", "experience", {}, "required", False),
        ("conditional_time", "requirements_text", "For senior: 5 years of experience with Java.", "experience", {}, "required", False),
        ("no_required_years", "requirements_text", "Must know Python", "experience", {}, "required", False),
        ("or_logic", "requirements_text", "Must know Python or Java", "logic", {"op": "any", "children": [{"op": "term", "term": "python"}, {"op": "term", "term": "java"}]}, "required", True),
        ("and_logic", "requirements_text", "Must know Python and SQL", "logic", {"op": "all", "children": [{"op": "term", "term": "python"}, {"op": "term", "term": "sql"}]}, "required", True),
        ("mixed_logic", "requirements_text", "Must know Python or Java and SQL", "logic", {}, "required", False),
        ("optional_skill", "requirements_text", "Experience with Python is a plus", "logic", {}, "required", False),
        ("unknown_tool", "requirements_text", "Must know SecretFramework", "logic", {}, "required", True),
        ("task_backend_vi", "tasks_text", "Xây dựng API quản lý hồ sơ.", "task", {"family": "backend_services"}, "observed", True),
        ("task_backend_en", "tasks_text", "Develop backend services.", "task", {"family": "backend_services"}, "observed", True),
        ("task_paraphrase", "tasks_text", "Implement HTTP endpoints for order processing.", "task", {"family": "backend_services"}, "observed", True),
        ("task_negated", "tasks_text", "We do not develop backend services.", "task", {}, "observed", False),
        ("tool_not_task", "tasks_text", "Python, FastAPI, SQL.", "task", {}, "observed", False),
        ("task_ui", "tasks_text", "Phát triển giao diện web cho trang đặt lịch.", "task", {"family": "user_interface"}, "observed", True),
        ("task_qa", "tasks_text", "Write test cases for the checkout flow.", "task", {"family": "quality_testing"}, "observed", True),
        ("task_analysis", "tasks_text", "Phân tích tỷ lệ khách hàng rời bỏ và giải thích biến động doanh thu.", "task", {"family": "data_analysis"}, "observed", True),
        ("no_total_to_tech", "requirements_text", "3 năm kinh nghiệm làm việc. Biết Python.", "experience", {"scope": "python"}, "required", False),
        ("cross_sentence_or", "requirements_text", "Must know Python. Or use Java.", "logic", {}, "required", False),
    ]
    result = []
    for name, field, text, kind, value, modality, present in rows:
        fields = {"title_for_matching": "", "tasks_text": "", "requirements_text": "", "preferred_requirements_text": ""}
        fields[field] = text
        result.append(dict(document_id="FIXTURE_"+name, kind="jd", fields=fields, source_sha256=source_hash(fields), exposure="development",
            origin="assistant_authored_contrastive_fixture_not_independent_gold",
            assertion=dict(kind=kind, value=value, modality=modality, present=present)))
    return result


def subset(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        def canonical(value):
            if isinstance(value, str):
                return value.casefold()
            if isinstance(value, dict):
                return {k: canonical(v) for k, v in value.items()}
            if isinstance(value, list):
                return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
            return value
        return isinstance(actual, list) and canonical(expected) == canonical(actual)
    if isinstance(expected, str):
        return isinstance(actual, str) and expected.casefold() == actual.casefold()
    return expected == actual


def score(documents, responses):
    by_id = {r["document_id"]: r for r in responses}
    results = []
    for doc in documents:
        assertion = doc["assertion"]
        response = by_id.get(doc["document_id"])
        if response is None:
            results.append(dict(document_id=doc["document_id"], status="missing_response", passed=False))
            continue
        found = any(c["kind"] == assertion["kind"] and c["modality"] == assertion["modality"] and c["polarity"] == "affirmative" and subset(assertion["value"], c["value"]) for c in response["claims"])
        results.append(dict(document_id=doc["document_id"], status="checked", passed=found == assertion["present"]))
    return dict(passed=sum(r["passed"] for r in results), total=len(results), cases=results,
        interpretation="Development assertion agreement only, not corpus accuracy, independent evaluation or ranking quality")
