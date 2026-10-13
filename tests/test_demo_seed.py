"""Member D demo-data reset tests (temporary directory per test, see conftest.py)."""
import json

from contracts import check_result
import demo_seed
import feedback
import storage


def history():
    return check_result(storage.load_history(demo_seed.DEMO_USER))["data"]["records"]


def test_first_use_scenario_is_empty():
    result = check_result(demo_seed.reset_demo_data("first_use"))
    assert result["status"] == "saved" and result["data"]["backup"] is None
    assert history() == []
    check_in = result["data"]["suggested_check_in"]
    assert check_result(feedback.build_feedback_context(check_in, []))["status"] == "ok"


def test_with_history_scenario_supports_the_next_day_flow():
    demo_seed.reset_demo_data("with_history")
    records = history()
    assert [r["decision"] for r in records] == ["rejected", "accepted"]
    previous = check_result(storage.load_previous("demo-user", "2026-10-11"))["data"]["latest_accepted"]
    assert previous["record_id"] == "demo-seed-2026-10-10"
    current = demo_seed.DEMO_CHECK_INS["with_history"]
    saved = storage.save_feedback("demo-user", previous["record_id"], {
        "completion": current["previous_completion"], "reported_date": current["date"],
        "pain_score": current["pain_score"], "fatigue_score": current["fatigue_score"]})
    assert saved["status"] == "saved"
    context = check_result(feedback.build_feedback_context(current, history()))["data"]["feedback_context"]
    assert context["previous_plan_id"] == "demo-seed-2026-10-10"
    assert context["completion"] == "Partly completed"
    logs = check_result(storage.load_logs("demo-user"))["data"]["events"]
    assert [e["human_decision"] for e in logs] == ["rejected", "accepted"]


def test_warning_scenario_input_is_listed():
    assert demo_seed.DEMO_CHECK_INS["warning"]["warning_signs"] == ["Numbness"]


def test_reset_backs_up_existing_and_corrupted_files(isolated_runtime_data):
    demo_seed.reset_demo_data("with_history")
    (isolated_runtime_data / "audit_log.json").write_text("corrupted", encoding="utf-8")
    result = check_result(demo_seed.reset_demo_data("first_use"))
    assert history() == []
    backup = isolated_runtime_data / "backups"
    [folder] = list(backup.iterdir())
    assert (folder / "audit_log.json").read_text(encoding="utf-8") == "corrupted"
    assert len(json.loads((folder / "records.json").read_text(encoding="utf-8"))["records"]) == 2
    assert result["data"]["backup"] == str(folder)


def test_unknown_scenario_changes_nothing(isolated_runtime_data):
    result = check_result(demo_seed.reset_demo_data("drop everything"))
    assert result["status"] == "error" and result["error_code"] == "INVALID_INPUT"
    assert not isolated_runtime_data.exists()


def test_command_line(capsys):
    assert demo_seed.main(["with_history"]) == 0
    assert '"scenario": "with_history"' in capsys.readouterr().out
    assert demo_seed.main(["--list"]) == 0
    assert "warning" in capsys.readouterr().out
