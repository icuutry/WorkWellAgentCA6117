"""Ten independent five-day runs with simulated model responses and no network.

Responses follow the actual recorded provider selections and curated advice,
but reasons and priorities are adapted to the simulated check-in and feedback.
Only the external model boundary is replaced; A/B/C/D and files are real.
"""
import copy
import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import app
import llm
import storage
from contracts import execution_groups, is_english_content


@pytest.mark.parametrize("repeat", range(10))
def test_five_consecutive_days_repeated_ten_times(repeat, monkeypatch):
    monkeypatch.setenv("WORKWELL_OFFLINE", "0")
    monkeypatch.setenv("WORKWELL_PROVIDER", "simulation-no-network")
    for name in ("ZHIPU_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_env_file", lambda: None)
    fixture = json.loads((Path(__file__).parent / "fixtures/provider_selections.json").read_text(encoding="utf-8"))
    templates = fixture["templates"]
    calls = []

    def simulated_model(provider, model, system, user):
        current = json.loads(user.split("CHECK_IN:\n", 1)[1].split("\n\nFEEDBACK", 1)[0])
        feedback = json.loads(user.split("may be empty):\n", 1)[1].split("\n\nSOURCES:\n", 1)[0])
        sources = json.loads(user.split("\n\nSOURCES:\n", 1)[1])
        offered = {a["action_id"] for source in sources for a in source["allowed_actions"]}
        available = [copy.deepcopy(a) for a in templates[len(calls) % 3] if a["action_id"] in offered]
        assert available
        count = min(len(available), 1 + ((repeat + len(calls)) % 3))
        selected = available[:count]
        if current["fatigue_score"] >= 5:
            selected.sort(key=lambda item: item["action_id"] != "ACT-KB-02")
        for rank, item in enumerate(selected, 1):
            item.update(priority=rank, reason="Simulated selection of an action supported by the retrieved source.",
                        priority_reason=f"Simulated rank {rank} using discomfort {current['pain_score']} and fatigue {current['fatigue_score']}.",
                        adjustment_reason=f"Simulated daily adaptation using {feedback['completion']} and the current scores.")
        calls.append({"current": current, "feedback": feedback, "count": count})
        return json.dumps({"selections": list(reversed(selected))})

    monkeypatch.setattr(llm, "_call_model", simulated_model)
    state = {}
    user_id = f"stress-user-{repeat + 1:02d}"
    scores = [(3, 4), (4, 6), (2, 3), (3, 5), (1, 2)]
    completion = ["Not applicable", "Partly completed", "Completed", "Not completed", "Partly completed"]
    daily_results = []
    previous_id = None
    for offset in range(5):
        current = {"user_id": user_id, "date": (date(2026, 10, 13) + timedelta(days=offset)).isoformat(),
                   "sitting_hours": 6.0 + (repeat % 2), "pain_location": "Neck" if repeat % 2 == 0 else "Shoulders",
                   "pain_score": scores[offset][0], "fatigue_score": scores[offset][1], "warning_signs": [],
                   "previous_completion": completion[offset]}
        backend = app.TeamBackend()
        level, _ = app.handle_action(state, backend, current, "generate")
        result = state["current"]["result"]
        assert result["status"] == "awaiting_confirmation", result
        assert len(calls) == offset + 1
        assert calls[-1]["feedback"]["previous_plan_id"] == previous_id
        actions = result["plan"]["actions"]
        assert len(actions) == calls[-1]["count"]
        assert [a["priority"] for a in actions] == list(range(1, len(actions) + 1))
        assert result["plan"]["execution_groups"] == execution_groups(actions)
        assert all(is_english_content(a[field]) for a in actions for field in
                   ("advice", "reason", "priority_reason", "adjustment_reason"))
        assert all(is_english_content(source[field]) for source in result["sources"]
                   for field in ("title", "content", "source_name"))
        app.handle_action(state, backend, current, "generate")
        recovered = {}
        app.handle_action(recovered, app.TeamBackend(), current, "generate")
        assert recovered["current"]["result"]["plan"] == result["plan"]
        assert len(calls) == offset + 1
        assert len(storage.load_history(user_id)["data"]["records"]) == offset + 1
        decision = "rejected" if offset in (1, 3) and repeat % 2 else "accepted"
        assert app.handle_action(state, backend, current, decision)[0] == "success"
        app.handle_action(state, backend, current, decision)
        assert len(calls) == offset + 1
        records = storage.load_history(user_id)["data"]["records"]
        logs = storage.load_logs(user_id)["data"]["events"]
        assert len(records) == offset + 1 and len(logs) == 2 * (offset + 1)
        assert records[-1]["decision"] == decision
        assert len({record["record_id"] for record in records}) == len(records)
        assert len({event["event_id"] for event in logs}) == len(logs)
        if previous_id:
            previous = next(record for record in records if record["record_id"] == previous_id)
            assert previous["completion_feedback"] == {
                "completion": current["previous_completion"], "reported_date": current["date"],
                "pain_score": current["pain_score"], "fatigue_score": current["fatigue_score"]}
        if decision == "accepted":
            previous_id = result["plan"]["plan_id"]
        importlib.reload(storage)
        assert app.TeamBackend().load_history(user_id) == records
        assert storage.load_history("unrelated-user")["data"]["records"] == []
        daily_results.append({"day": offset + 1, "date": current["date"], "actions": len(actions),
                              "decision": decision, "records": len(records), "audit_events": len(logs), "status": "passed"})
    output = Path(__file__).parents[1] / "artifacts/five_day_stress_results.json"
    output.parent.mkdir(exist_ok=True)
    summary = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    summary[str(repeat + 1)] = {"days": daily_results, "simulated_model_requests": len(calls), "real_api_requests": 0}
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
