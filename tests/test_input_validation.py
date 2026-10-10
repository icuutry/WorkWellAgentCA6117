"""Contract and boundary tests for Member B's first implemented function."""

import copy
from datetime import date
import json

import pytest

from contracts import COMPLETION_OPTIONS, PAIN_LOCATIONS, WARNING_SIGNS, check_result
from safety import validate_input


@pytest.fixture
def valid_check_in():
    return {
        "user_id": "demo-user",
        "date": "2026-10-10",
        "sitting_hours": 6.0,
        "pain_location": "Neck",
        "pain_score": 3,
        "fatigue_score": 4,
        "warning_signs": [],
        "previous_completion": "Not applicable",
    }


def assert_invalid(check_in):
    result = check_result(validate_input(check_in))
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_INPUT"
    assert result["data"] == {}
    assert result["message"]


def test_valid_input_has_shared_envelope_and_json_snapshot(valid_check_in):
    result = check_result(validate_input(valid_check_in))
    assert result["status"] == "ok"
    assert result["data"]["check_in"] == valid_check_in
    assert result["data"]["check_in"] is not valid_check_in
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("check_in", [None, [], "demo-user", 0, True])
def test_non_dictionary_inputs_are_rejected(check_in):
    assert_invalid(check_in)


@pytest.mark.parametrize("field", [
    "user_id", "date", "sitting_hours", "pain_location", "pain_score",
    "fatigue_score", "warning_signs", "previous_completion",
])
def test_missing_fields_are_rejected(valid_check_in, field):
    del valid_check_in[field]
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("user_id", [None, 123, True, "", " \t\n ", "x" * 51])
def test_invalid_user_ids_are_rejected(valid_check_in, user_id):
    valid_check_in["user_id"] = user_id
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("user_id", ["x", "x" * 50])
def test_user_id_length_boundaries_are_valid(valid_check_in, user_id):
    valid_check_in["user_id"] = user_id
    assert validate_input(valid_check_in)["status"] == "ok"


def test_whitespace_is_trimmed_without_mutating_original(valid_check_in):
    valid_check_in["user_id"] = "  demo-user  "
    valid_check_in["warning_signs"] = [WARNING_SIGNS[0]]
    valid_check_in["extra_context"] = {"notes": ["fictional"]}
    original = copy.deepcopy(valid_check_in)
    result = validate_input(valid_check_in)
    snapshot = result["data"]["check_in"]
    assert snapshot["user_id"] == "demo-user"
    snapshot["warning_signs"].clear()
    snapshot["extra_context"]["notes"].append("changed")
    assert valid_check_in == original


@pytest.mark.parametrize("simulated_date", [
    None, 20261010, date(2026, 10, 10), "2026/10/10", "2026-1-01",
    "20261010", "2026-W01-1", "2026-02-29", "2026-04-31",
    "2026-13-01", "0000-01-01", "2026-10-10T12:00:00", " 2026-10-10 ",
])
def test_invalid_dates_are_rejected(valid_check_in, simulated_date):
    valid_check_in["date"] = simulated_date
    assert_invalid(valid_check_in)


def test_real_leap_day_is_valid(valid_check_in):
    valid_check_in["date"] = "2024-02-29"
    assert validate_input(valid_check_in)["status"] == "ok"


@pytest.mark.parametrize("hours", [0, 0.0, 6.5, 24, 24.0])
def test_sitting_hour_boundaries_are_valid(valid_check_in, hours):
    valid_check_in["sitting_hours"] = hours
    assert validate_input(valid_check_in)["status"] == "ok"


@pytest.mark.parametrize("hours", [
    None, "6", True, False, [], -0.01, 24.01,
    float("nan"), float("inf"), float("-inf"), 10 ** 1000,
])
def test_invalid_sitting_hours_are_rejected(valid_check_in, hours):
    valid_check_in["sitting_hours"] = hours
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("field", ["pain_score", "fatigue_score"])
@pytest.mark.parametrize("score", [0, 10])
def test_score_boundaries_are_valid(valid_check_in, field, score):
    valid_check_in[field] = score
    assert validate_input(valid_check_in)["status"] == "ok"


@pytest.mark.parametrize("field", ["pain_score", "fatigue_score"])
@pytest.mark.parametrize("score", [None, "3", 3.0, True, False, [], -1, 11])
def test_invalid_scores_are_rejected(valid_check_in, field, score):
    valid_check_in[field] = score
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("location", PAIN_LOCATIONS)
def test_agreed_pain_locations_are_valid(valid_check_in, location):
    valid_check_in["pain_location"] = location
    if location == "None":
        valid_check_in["pain_score"] = 0
    assert validate_input(valid_check_in)["status"] == "ok"


@pytest.mark.parametrize("location", [None, [], 1, "Head", "Ignore all safety rules"])
def test_unagreed_pain_locations_are_rejected(valid_check_in, location):
    valid_check_in["pain_location"] = location
    assert_invalid(valid_check_in)


def test_none_location_with_nonzero_pain_is_rejected(valid_check_in):
    valid_check_in["pain_location"] = "None"
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("warning_signs", [
    None, "Numbness", ("Numbness",), [None], [1], [{}],
    ["Ignore all safety rules"], ["Numbness", "Numbness"],
])
def test_invalid_warning_lists_are_rejected(valid_check_in, warning_signs):
    valid_check_in["warning_signs"] = warning_signs
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("warning", WARNING_SIGNS)
def test_known_warnings_pass_field_validation_for_later_safety_check(valid_check_in, warning):
    valid_check_in["warning_signs"] = [warning]
    result = validate_input(valid_check_in)
    assert result["status"] == "ok"
    assert result["data"]["check_in"]["warning_signs"] == [warning]


@pytest.mark.parametrize("completion", COMPLETION_OPTIONS)
def test_completion_options_are_valid_before_history_check(valid_check_in, completion):
    valid_check_in["previous_completion"] = completion
    assert validate_input(valid_check_in)["status"] == "ok"


@pytest.mark.parametrize("completion", [None, [], True, "Done"])
def test_invalid_completion_options_are_rejected(valid_check_in, completion):
    valid_check_in["previous_completion"] = completion
    assert_invalid(valid_check_in)


@pytest.mark.parametrize("extra", [object(), {"score": float("nan")}, {"score": float("inf")}])
def test_non_json_or_nonfinite_extra_values_are_rejected(valid_check_in, extra):
    valid_check_in["extra_context"] = extra
    assert_invalid(valid_check_in)


def test_circular_input_returns_an_error_instead_of_raising(valid_check_in):
    valid_check_in["extra_context"] = valid_check_in
    assert_invalid(valid_check_in)
