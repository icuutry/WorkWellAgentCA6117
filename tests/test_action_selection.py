"""Test explicit priorities, daily adaptation and conservative grouping without API calls."""
import copy
import json
import pytest
import llm
import retrieval
import safety
from contracts import execution_groups


def allowed():
    return llm.build_allowed_actions(retrieval.load_knowledge())


def choice(action_id="ACT-KB-07", priority=1, **changes):
    return {"action_id": action_id, "priority": priority, "reason": "Supported workday habit.",
            "priority_reason": "Focus on the reported discomfort.",
            "adjustment_reason": "Use current daily completion feedback."} | changes


def parse(selected, completion="Not applicable"):
    return llm.parse_selection(json.dumps({"selections": selected}), allowed(),
                              {"completion": completion, "previous_plan_id": "previous-test-plan"})


def plan(actions):
    return {"plan_id": "test-plan", "actions": actions, "execution_groups": execution_groups(actions)}


def test_all_catalog_actions_pass_source_validator():
    for candidate in allowed():
        actions = parse([choice(candidate["action_id"])])
        assert safety.validate_plan(plan(actions), retrieval.load_knowledge())["status"] == "ok"


@pytest.mark.parametrize("bad", [choice("UNKNOWN"), choice(advice="Stretch every hour."),
    choice(reason=""), choice(action_id=[]), choice(priority=True), choice(priority=0),
    choice(priority_reason=""), choice(adjustment_reason="")])
def test_invalid_selection_is_refused(bad):
    with pytest.raises(ValueError): parse([bad])


def test_unretrieved_action_is_unavailable():
    sources = [s for s in retrieval.load_knowledge() if s["id"] == "KB-02"]
    with pytest.raises(ValueError):
        llm.parse_selection(json.dumps({"selections": [choice()]}), llm.build_allowed_actions(sources), {})


@pytest.mark.parametrize("completion", ["Partly completed", "Not completed"])
def test_incomplete_feedback_does_not_discard_supported_actions(completion):
    actions = parse([choice("ACT-KB-02", 2), choice("ACT-KB-07", 1)], completion)
    assert len(actions) == 2
    assert [a["priority"] for a in actions] == [1, 2]
    assert actions[0]["source_ids"] == ["KB-07"]


@pytest.mark.parametrize("selected", [[choice(), choice("ACT-KB-02")],
    [choice(), choice("ACT-KB-02", 3)], [choice(), choice("ACT-KB-07", 2)]])
def test_duplicate_or_missing_priorities_and_duplicate_ids_are_refused(selected):
    with pytest.raises(ValueError): parse(selected)


def test_advice_is_curated_and_explanations_are_preserved():
    actions = parse([choice("ACT-KB-02", priority_reason="Fatigue rose from four to six.",
                            adjustment_reason="Keep this manageable after partial completion.")])
    candidate = next(a for a in allowed() if a["action_id"] == "ACT-KB-02")
    assert actions[0]["advice"] == candidate["advice"]
    assert actions[0]["priority_reason"] == "Fatigue rose from four to six."
    assert "partial completion" in actions[0]["adjustment_reason"]


def test_top_complementary_actions_are_grouped_without_losing_sources():
    actions = parse([choice("ACT-KB-02", 2), choice("ACT-KB-07", 1), choice("ACT-KB-04", 3)])
    result = plan(actions)
    assert result["execution_groups"][0]["action_priorities"] == [1, 2]
    assert result["execution_groups"][1]["action_priorities"] == [3]
    assert len(result["actions"]) == 3
    assert {a["source_ids"][0] for a in result["actions"]} == {"KB-02", "KB-07", "KB-04"}
    assert safety.validate_plan(result, retrieval.load_knowledge())["status"] == "ok"


def test_different_categories_remain_separate():
    actions = parse([choice("ACT-KB-07", 1), choice("ACT-KB-04", 2)])
    assert [g["action_priorities"] for g in execution_groups(actions)] == [[1], [2]]


@pytest.mark.parametrize("change", ["discard", "duplicate", "invent_merge"])
def test_tampered_execution_groups_are_rejected(change):
    result = plan(parse([choice("ACT-KB-07", 1), choice("ACT-KB-04", 2)]))
    if change == "discard": result["execution_groups"].pop()
    elif change == "duplicate": result["execution_groups"][1]["action_priorities"] = [1]
    else: result["execution_groups"] = [{"group_id": "g", "action_priorities": [1, 2], "title": "Combined", "merge_reason": "Invented grouping."}]
    assert safety.validate_plan(result, retrieval.load_knowledge())["error_code"] == "INVALID_MODEL_OUTPUT"


def test_non_english_source_is_blocked_before_generation():
    sources = copy.deepcopy(retrieval.load_knowledge())
    sources[0]["content"] = chr(0x4e2d) + chr(0x6587)
    assert retrieval.retrieve_guidance({"sitting_hours": 6}, knowledge=sources)["status"] == "error"
    assert safety.validate_plan(plan(parse([choice()])), sources)["error_code"] == "INVALID_MODEL_OUTPUT"


def test_clinical_text_in_adjustment_reason_is_rejected():
    result = plan(parse([choice(adjustment_reason="Take medication for the discomfort.")]))
    assert safety.validate_plan(result, retrieval.load_knowledge())["error_code"] == "INVALID_MODEL_OUTPUT"


def test_first_day_cannot_claim_an_unchanged_historical_score():
    selected = [choice(adjustment_reason="No change in pain score, so keep the previous priority.")]
    actions = llm.parse_selection(json.dumps({"selections": selected}), allowed(), {"previous_plan_id": None})
    assert actions[0]["adjustment_reason"] == "First daily plan; no previous accepted plan or completion feedback exists."


@pytest.mark.parametrize("reason", ["No significant change in fatigue score.", "Increased activity has helped reduce fatigue."])
def test_daily_facts_override_detected_contradiction_or_causal_claim(reason):
    context = {"previous_plan_id": "old", "completion": "Completed", "previous_pain_score": 3,
               "current_pain_score": 2, "previous_fatigue_score": 6, "current_fatigue_score": 3}
    note = llm.daily_adjustment_note(reason, context)
    assert "fatigue 6/10 to 3/10" in note and "does not establish" in note
    assert reason not in note


def test_non_english_source_name_is_refused():
    sources = copy.deepcopy(retrieval.load_knowledge())
    sources[0]["source_name"] = chr(0x4e2d) + chr(0x6587)
    assert retrieval.retrieve_guidance({"sitting_hours": 6}, knowledge=sources)["status"] == "error"
    assert safety.validate_plan(plan(parse([choice()])), sources)["error_code"] == "INVALID_MODEL_OUTPUT"


def test_page_displays_grouping_priorities_and_daily_reasons(monkeypatch):
    from datetime import date
    from streamlit.testing.v1 import AppTest
    import app
    monkeypatch.setenv("WORKWELL_OFFLINE", "0")
    monkeypatch.setattr(llm, "load_env_file", lambda: None)
    monkeypatch.setattr(llm, "_call_model", lambda *args: json.dumps({"selections": [
        choice("ACT-KB-01", 2), choice("ACT-KB-07", 1)]}))
    ui = AppTest.from_file(app.__file__, default_timeout=20).run()
    ui.date_input[0].set_value(date(2026, 10, 13))
    ui.selectbox[0].set_value("Neck")
    ui.slider[0].set_value(3)
    ui.button[0].click().run()
    assert not ui.exception
    assert ui.session_state["current"]["result"]["status"] == "awaiting_confirmation"
    displayed = "\n".join(item.value for item in ui.markdown)
    assert "Combined priority work break" in displayed
    assert "Priority rationale" in displayed and "Daily adjustment" in displayed


@pytest.mark.parametrize("field", ["reason", "priority_reason", "adjustment_reason"])
def test_model_explanations_with_non_english_script_are_rejected(field):
    with pytest.raises(ValueError):
        parse([choice(**{field: "English " + chr(0x4e2d) + chr(0x6587)})])


def test_non_english_catalog_advice_is_rejected_before_model_call(tmp_path, monkeypatch):
    catalog = json.loads(llm.ACTION_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog[0]["advice"] = chr(0x4e2d) + chr(0x6587)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(llm, "ACTION_CATALOG_PATH", path)
    with pytest.raises(ValueError): allowed()
