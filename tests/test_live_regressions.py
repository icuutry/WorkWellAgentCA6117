"""Regressions from real-provider output; these tests make no API calls."""
import pytest
import safety


SOURCE = {"id": "KB-07", "title": "Gentle stretches", "category": "break",
          "content": "Slow, gentle neck and shoulder stretches can ease desk stiffness.",
          "url": "https://www.ccohs.ca/oshanswers/ergonomics/office/index.html"}


def plan(advice):
    return {"plan_id": "regression-plan", "actions": [{"category": "break", "advice": advice,
            "reason": "General workday guidance from the retrieved source.", "source_ids": ["KB-07"]}]}


def test_generic_break_label_with_supported_specific_action():
    result = safety.validate_plan(plan("Perform gentle neck stretches during short breaks."), [SOURCE])
    assert result["status"] == "ok"


@pytest.mark.parametrize("advice", ["Take short breaks.",
    "Walk and stretch during short breaks.", "Stretch every 30 minutes.",
    "Stretch every hour.", "Take a one-minute stretching break.",
    "Take a thirty-minute stretching break.",
    "Take medication and stretch during short breaks."])
def test_generic_label_does_not_allow_unsupported_actions_or_schedules(advice):
    assert safety.validate_plan(plan(advice), [SOURCE])["error_code"] == "INVALID_MODEL_OUTPUT"


def test_source_without_curated_break_category_keeps_strict_cues():
    source = {k: v for k, v in SOURCE.items() if k != "category"}
    assert safety.validate_plan(plan("Stretch during short breaks."), [source])["error_code"] == "INVALID_MODEL_OUTPUT"


def test_number_word_duration_matches_equivalent_digit_source():
    source = SOURCE | {"content": "Gentle stretches for 1 minute during a work break."}
    assert safety.validate_plan(plan("Stretch for one minute during a break."), [source])["status"] == "ok"


def test_implicit_and_spelled_intervals_are_detected():
    from decimal import Decimal
    assert safety._time_durations("Walk every hour, rest for one minute, then look away for twenty seconds.") == {
        Decimal(3600), Decimal(60), Decimal(20)}
