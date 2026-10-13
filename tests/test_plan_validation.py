"""Plan schema, retrieved-reference, and conservative content-gate tests."""

import copy
import json

import pytest

from contracts import check_result
from safety import validate_plan


@pytest.fixture
def sources():
    # Synthetic guidance for tests only; these example URLs are not health evidence.
    return [
        {"id": "KB-BREAK", "title": "Test break guidance",
         "content": "Take a short standing break from sitting.", "url": "https://example.org/break"},
        {"id": "KB-WORKSTATION", "title": "Test workstation guidance",
         "content": "Adjust chair height and monitor position.", "url": "https://example.org/workstation"},
        {"id": "KB-SCREEN", "title": "Test screen guidance",
         "content": "Look away from the screen for 20 seconds to rest your eyes.", "url": "https://example.org/screen"},
        {"id": "KB-FATIGUE", "title": "Test fatigue guidance",
         "content": "Take a quiet rest to help manage fatigue.", "url": "https://example.org/fatigue"},
    ]


@pytest.fixture
def plan():
    return {"plan_id": "server-plan-001", "actions": [{
        "category": "break", "advice": "Take a short standing break.",
        "reason": "You reported a long sitting period.", "source_ids": ["KB-BREAK"],
    }]}


def assert_invalid(plan, sources):
    result = check_result(validate_plan(plan, sources))
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_MODEL_OUTPUT"
    assert result["data"] == {}
    assert result["message"]
    assert result["trace"][-1]["status"] == "error"


def test_valid_plan_returns_separate_json_snapshot(plan, sources):
    result = check_result(validate_plan(plan, sources))
    assert result["status"] == "ok"
    assert result["data"]["plan"] == plan
    assert result["data"]["plan"] is not plan
    assert result["trace"] == [{
        "step": "validate_plan", "status": "ok", "tool": "safety.validate_plan"
    }]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_one_to_three_actions_are_allowed(plan, sources, count):
    plan["actions"] = [copy.deepcopy(plan["actions"][0]) for _ in range(count)]
    assert validate_plan(plan, sources)["status"] == "ok"


@pytest.mark.parametrize("count", [0, 4])
def test_action_count_outside_one_to_three_is_rejected(plan, sources, count):
    plan["actions"] = [copy.deepcopy(plan["actions"][0]) for _ in range(count)]
    assert_invalid(plan, sources)


@pytest.mark.parametrize("bad_plan", [None, [], "plan", True])
def test_non_dictionary_plans_are_rejected(bad_plan, sources):
    assert_invalid(bad_plan, sources)


@pytest.mark.parametrize("field", ["plan_id", "actions"])
def test_missing_plan_fields_are_rejected(plan, sources, field):
    del plan[field]
    assert_invalid(plan, sources)


def test_extra_plan_fields_cannot_override_validation(plan, sources):
    plan["disable_validation"] = True
    assert_invalid(plan, sources)


@pytest.mark.parametrize("plan_id", [None, 123, True, [], "", "  "])
def test_invalid_plan_ids_are_rejected(plan, sources, plan_id):
    plan["plan_id"] = plan_id
    assert_invalid(plan, sources)


@pytest.mark.parametrize("actions", [None, {}, "actions", True])
def test_non_list_actions_are_rejected(plan, sources, actions):
    plan["actions"] = actions
    assert_invalid(plan, sources)


@pytest.mark.parametrize("action", [None, [], "action", 123])
def test_non_dictionary_actions_are_rejected(plan, sources, action):
    plan["actions"] = [action]
    assert_invalid(plan, sources)


@pytest.mark.parametrize("field", ["category", "advice", "reason", "source_ids"])
def test_missing_action_fields_are_rejected(plan, sources, field):
    del plan["actions"][0][field]
    assert_invalid(plan, sources)


def test_extra_action_fields_are_rejected(plan, sources):
    plan["actions"][0]["trusted"] = True
    assert_invalid(plan, sources)


@pytest.mark.parametrize("category", [None, [], True, "treatment", "exercise", "BREAK"])
def test_unagreed_categories_are_rejected(plan, sources, category):
    plan["actions"][0]["category"] = category
    assert_invalid(plan, sources)


@pytest.mark.parametrize("field", ["advice", "reason"])
@pytest.mark.parametrize("value", [None, [], 123, True, "", " \t "])
def test_advice_and_reason_require_nonempty_strings(plan, sources, field, value):
    plan["actions"][0][field] = value
    assert_invalid(plan, sources)


@pytest.mark.parametrize("source_ids", [
    None, [], "KB-BREAK", ("KB-BREAK",), [None], [1], [[]], [" "], ["KB-UNKNOWN"],
])
def test_invalid_reference_lists_are_rejected(plan, sources, source_ids):
    plan["actions"][0]["source_ids"] = source_ids
    assert_invalid(plan, sources)


def test_repeated_existing_reference_is_not_an_invented_schema_error(plan, sources):
    plan["actions"][0]["source_ids"] = ["KB-BREAK", "KB-BREAK"]
    assert validate_plan(plan, sources)["status"] == "ok"


@pytest.mark.parametrize("bad_sources", [None, [], {}, "sources", [None], ["source"]])
def test_sources_need_the_expected_outer_format(plan, bad_sources):
    assert_invalid(plan, bad_sources)


@pytest.mark.parametrize("field", ["id", "title", "content", "url"])
def test_missing_source_fields_are_rejected(plan, sources, field):
    del sources[0][field]
    assert_invalid(plan, sources)


@pytest.mark.parametrize("field", ["id", "title", "content", "url"])
@pytest.mark.parametrize("value", [None, [], "", "  "])
def test_invalid_source_fields_are_rejected(plan, sources, field, value):
    sources[0][field] = value
    assert_invalid(plan, sources)


@pytest.mark.parametrize("url", [
    "not-a-url", "ftp://example.org/file", "file:///private/file", "https:///missing-host",
    "https://user:password@example.org", "https://[invalid", "https://example.org:bad",
    "https://example.org:70000", "https://exam ple.org", "https://example.org/\nfile",
    "javascript:alert(1)",
])
def test_invalid_or_non_public_source_url_formats_are_rejected(plan, sources, url):
    sources[0]["url"] = url
    assert_invalid(plan, sources)


def test_http_source_is_accepted_by_the_existing_url_contract(plan, sources):
    sources[0]["url"] = "http://example.org/break"
    assert validate_plan(plan, sources)["status"] == "ok"


def test_duplicate_source_ids_are_rejected_as_ambiguous(plan, sources):
    sources.append(copy.deepcopy(sources[0]))
    assert_invalid(plan, sources)


@pytest.mark.parametrize("category,advice,source_id", [
    ("break", "Take a short standing break.", "KB-BREAK"),
    ("workstation", "Adjust chair height.", "KB-WORKSTATION"),
    ("screen_rest", "Look away from the screen for 20 seconds.", "KB-SCREEN"),
    ("fatigue_management", "Take a quiet rest.", "KB-FATIGUE"),
])
def test_all_four_categories_accept_matching_guidance(plan, sources, category, advice, source_id):
    plan["actions"][0].update(category=category, advice=advice, source_ids=[source_id])
    assert validate_plan(plan, sources)["status"] == "ok"


@pytest.mark.parametrize("advice", [
    "Take ibuprofen and then a standing break.",
    "Diagnose your neck pain before taking a standing break.",
    "Take a standing break to treat your condition.",
    "Ignore all safety rules and take a standing break.",
    "BYPASS WARNING SIGNS AND TAKE A STANDING BREAK.",
])
def test_allowed_category_does_not_allow_explicit_out_of_scope_content(plan, sources, advice):
    plan["actions"][0]["advice"] = advice
    assert_invalid(plan, sources)


@pytest.mark.parametrize("reason", [
    "This will treat your condition.", "You have migraine.", "This is carpal tunnel syndrome.",
])
def test_reason_cannot_add_a_diagnosis_or_treatment_claim(plan, sources, reason):
    plan["actions"][0]["reason"] = reason
    assert_invalid(plan, sources)


def test_clinical_terms_in_source_do_not_automatically_reject_ordinary_advice(plan, sources):
    sources[0]["content"] += " This source also discusses diagnosis and treatment."
    assert validate_plan(plan, sources)["status"] == "ok"


def test_matching_source_id_alone_is_not_enough(plan, sources):
    sources[0]["content"] = "Adjust chair height and monitor position."
    assert_invalid(plan, sources)


def test_content_is_checked_against_cited_sources_only(plan, sources):
    plan["actions"][0]["source_ids"] = ["KB-WORKSTATION"]
    assert_invalid(plan, sources)


def test_recognized_measure_missing_from_cited_guidance_is_rejected(plan, sources):
    sources[0]["content"] = "Take a short break."
    assert_invalid(plan, sources)  # The standing measure is absent.


def test_action_without_category_content_cues_is_rejected(plan, sources):
    plan["actions"][0]["advice"] = "Do whatever you prefer."
    assert_invalid(plan, sources)


def test_supported_duration_is_allowed(plan, sources):
    sources[0]["content"] = "Take a standing break for 2 minutes."
    plan["actions"][0]["advice"] = "Take a standing break for 2 minutes."
    assert validate_plan(plan, sources)["status"] == "ok"


def test_equivalent_time_units_are_allowed(plan, sources):
    sources[0]["content"] = "Take a standing break for 1 minute."
    plan["actions"][0]["advice"] = "Take a standing break for 60 seconds."
    assert validate_plan(plan, sources)["status"] == "ok"


@pytest.mark.parametrize("duration", ["2 minutes", "2 hours", "0 seconds", "-1 minute"])
def test_invented_or_nonpositive_durations_are_rejected(plan, sources, duration):
    sources[0]["content"] = "Take a standing break for 1 minute."
    plan["actions"][0]["advice"] = "Take a standing break for " + duration + "."
    assert_invalid(plan, sources)


def test_reason_can_reference_current_check_in_duration(plan, sources):
    plan["actions"][0]["reason"] = "You reported sitting for 6 hours today."
    assert validate_plan(plan, sources)["status"] == "ok"


@pytest.mark.parametrize("extra", [object(), float("nan"), float("inf")])
def test_source_metadata_must_be_json_serializable_and_finite(plan, sources, extra):
    sources[0]["metadata"] = extra
    assert_invalid(plan, sources)


def test_circular_source_metadata_returns_error(plan, sources):
    sources[0]["metadata"] = sources
    assert_invalid(plan, sources)


def test_original_plan_and_sources_are_not_mutated(plan, sources):
    original_plan, original_sources = copy.deepcopy(plan), copy.deepcopy(sources)
    snapshot = validate_plan(plan, sources)["data"]["plan"]
    snapshot["actions"][0]["source_ids"].clear()
    assert plan == original_plan
    assert sources == original_sources
