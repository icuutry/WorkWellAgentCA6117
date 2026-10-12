import json

import pytest

import llm
import retrieval
from contracts import ACTION_CATEGORIES, check_result

NECK = {"user_id": "u1", "date": "2026-10-08", "sitting_hours": 7, "pain_location": "Neck", "pain_score": 6,
        "fatigue_score": 3, "warning_signs": [], "previous_completion": "Not applicable"}
FB = {"previous_plan_id": None, "previous_actions": [], "completion": "Not applicable"}


def sources_for(ci):
    return retrieval.retrieve_guidance(ci)["data"]["sources"]


def test_knowledge_base_is_valid_and_sized():
    items = retrieval.load_knowledge()
    assert 10 <= len(items) <= 15
    assert len({i["id"] for i in items}) == len(items)
    assert all(i["url"].startswith("https://") for i in items)
    assert all(i["category"] in ACTION_CATEGORIES | {"reference_only"} for i in items)


def test_neck_match_has_contract_fields():
    r = check_result(retrieval.retrieve_guidance(NECK))
    ids = [s["id"] for s in r["data"]["sources"]]
    assert r["status"] == "ok" and "KB-04" in ids and len(ids) <= 5
    assert all(s["id"] and s["title"] and s["content"] and s["url"] for s in r["data"]["sources"])


def test_no_match_is_ok_and_empty():
    r = retrieval.retrieve_guidance({"sitting_hours": 1, "pain_location": "None", "pain_score": 0, "fatigue_score": 1})
    assert r["status"] == "ok" and r["data"]["sources"] == []


def test_eyes_vs_wrists_differ():
    a = sources_for({"pain_location": "Eyes", "pain_score": 5})
    b = sources_for({"pain_location": "Wrists", "pain_score": 5})
    assert a[0]["id"] == "KB-06" and [s["id"] for s in a] != [s["id"] for s in b]


def test_feedback_changes_retrieval():
    base = {"pain_location": "None", "pain_score": 0, "sitting_hours": 1, "fatigue_score": 1}
    assert sources_for(dict(base, previous_completion="Completed")) == []
    assert sources_for(dict(base, previous_completion="Not completed"))


def test_reference_only_never_returned():
    r = sources_for({"pain_location": "Neck", "pain_score": 9, "sitting_hours": 9, "fatigue_score": 9})
    assert all(s["category"] != "reference_only" for s in r)


def test_corrupt_kb_is_storage_error(tmp_path, monkeypatch):
    p = tmp_path / "k.json"; p.write_text("{bad")
    monkeypatch.setattr(retrieval, "KNOWLEDGE_PATH", p)
    r = check_result(retrieval.retrieve_guidance(NECK))
    assert r["status"] == "error" and r["error_code"] == "STORAGE_ERROR"


def test_no_sources_refused():
    assert llm.generate_plan(NECK, FB, [])["error_code"] == "NO_SOURCES"


def good_json(src):
    return json.dumps({"actions": [{"category": "workstation", "advice": "a", "reason": "r", "source_ids": [src[0]["id"]]}]})


def test_live_path_with_mocked_model(monkeypatch):
    src = sources_for(NECK)
    monkeypatch.setattr(llm, "_call_model", lambda *a: "```json\n" + good_json(src) + "\n```")
    r = check_result(llm.generate_plan(NECK, FB, src))
    assert r["status"] == "ok" and r["data"]["mode"] == "live"
    assert r["data"]["plan"]["plan_id"].startswith("plan-")


@pytest.mark.parametrize("bad", [
    "not json",
    '{"actions": []}',
    '{"actions": [{"category": "diagnosis", "advice": "a", "reason": "r", "source_ids": ["KB-04"]}]}',
    '{"actions": [{"category": "break", "advice": "a", "reason": "r", "source_ids": ["KB-99"]}]}',
    '{"actions": [{"category": "break", "advice": "a", "reason": "r", "source_ids": []}]}',
])
def test_invalid_model_output(monkeypatch, bad):
    monkeypatch.setattr(llm, "_call_model", lambda *a: bad)
    r = check_result(llm.generate_plan(NECK, FB, sources_for(NECK)))
    assert r["error_code"] == "INVALID_MODEL_OUTPUT"


def test_more_than_three_actions_rejected(monkeypatch):
    src = sources_for(NECK)
    a = {"category": "break", "advice": "a", "reason": "r", "source_ids": [src[0]["id"]]}
    monkeypatch.setattr(llm, "_call_model", lambda *x: json.dumps({"actions": [a] * 4}))
    assert llm.generate_plan(NECK, FB, src)["error_code"] == "INVALID_MODEL_OUTPUT"


def test_api_failure_does_not_leak_details(monkeypatch):
    def boom(*a): raise RuntimeError("secret-key-123")
    monkeypatch.setattr(llm, "_call_model", boom)
    r = check_result(llm.generate_plan(NECK, FB, sources_for(NECK)))
    assert r["error_code"] == "MODEL_ERROR" and "secret-key-123" not in r["message"]


def test_offline_is_marked(monkeypatch):
    monkeypatch.setenv("WORKWELL_OFFLINE", "1")
    r = check_result(llm.generate_plan(NECK, FB, sources_for(NECK)))
    assert r["data"]["mode"] == "offline_demo" and 1 <= len(r["data"]["plan"]["actions"]) <= 3


def test_feedback_and_sources_reach_prompt():
    fb = dict(FB, completion="Not completed", previous_actions=["Stretch every hour"])
    msg = llm.build_user_message(NECK, fb, sources_for(NECK))
    assert "Not completed" in msg and "Stretch every hour" in msg and "KB-04" in msg


def test_env_file_loaded_without_overriding(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text('# c\nWW_TEST_A="from-file"\nWW_TEST_B=file-b\nWW_EMPTY=\n')
    monkeypatch.setenv("WW_TEST_B", "from-env")
    monkeypatch.delenv("WW_TEST_A", raising=False)
    monkeypatch.delenv("WW_EMPTY", raising=False)
    llm.load_env_file(str(p))
    import os
    assert os.environ["WW_TEST_A"] == "from-file"
    assert os.environ["WW_TEST_B"] == "from-env"
    assert "WW_EMPTY" not in os.environ
    monkeypatch.delenv("WW_TEST_A")


def test_missing_env_file_is_fine(tmp_path):
    llm.load_env_file(str(tmp_path / "nope"))
