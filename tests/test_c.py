import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import llm, retrieval

NECK = {"user_id": "u1", "sitting_hours": 7, "discomfort_area": "neck", "discomfort_score": 6, "fatigue_score": 3}


def test_match_neck():
    r = retrieval.retrieve_guidance(NECK)
    ids = [s["id"] for s in r["sources"]]
    assert r["status"] == "ok" and "K04" in ids and len(ids) <= 5

def test_no_match():
    r = retrieval.retrieve_guidance({"sitting_hours": 1, "discomfort_score": 0, "fatigue_score": 1})
    assert r["status"] == "ok" and r["sources"] == []

def test_eyes_differs_from_wrist():
    a = [s["id"] for s in retrieval.retrieve_guidance({"discomfort_area": "eyes", "discomfort_score": 5})["sources"]]
    b = [s["id"] for s in retrieval.retrieve_guidance({"discomfort_area": "wrist", "discomfort_score": 5})["sources"]]
    assert a[0] == "K06" and a != b

def test_corrupt_kb(tmp_path, monkeypatch):
    p = tmp_path / "k.json"; p.write_text("{bad")
    monkeypatch.setattr(retrieval, "KNOWLEDGE_PATH", p)
    assert retrieval.retrieve_guidance(NECK)["status"] == "error"

def test_no_sources_refused():
    assert llm.generate_plan(NECK, {}, [])["error"] == "no_sources"

def test_parse_ok_and_fenced():
    t = 'Sure:\n```json\n{"items":[{"category":"stretching","advice":"a","reason":"r","source_ids":["K07"]}]}\n```'
    assert llm.parse_plan(t)["items"][0]["source_ids"] == ["K07"]

def test_bad_output(monkeypatch):
    monkeypatch.setattr(llm, "_call_model", lambda *a: "not json")
    src = retrieval.retrieve_guidance(NECK)["sources"]
    assert llm.generate_plan(NECK, {}, src)["error"] == "bad_model_output"

def test_call_failure(monkeypatch):
    def boom(*a): raise RuntimeError("no key")
    monkeypatch.setattr(llm, "_call_model", boom)
    src = retrieval.retrieve_guidance(NECK)["sources"]
    assert llm.generate_plan(NECK, {}, src)["error"] == "llm_call_failed"

def test_offline_marked(monkeypatch):
    monkeypatch.setenv("WORKWELL_OFFLINE", "1")
    src = retrieval.retrieve_guidance(NECK)["sources"]
    r = llm.generate_plan(NECK, {}, src)
    assert r["mode"] == "offline_demo" and len(r["plan"]["items"]) <= 3

def test_history_in_prompt():
    h = {"previous_plan": "x", "completion": "none"}
    msg = llm.build_user_message(NECK, h, retrieval.retrieve_guidance(NECK)["sources"])
    assert "completion" in msg and "K04" in msg
