"""Member D: initialise or reset simulated demo data for the three demo scenarios.

Run from the repository root:

    python demo_seed.py first_use      # empty storage: first use, no history
    python demo_seed.py with_history   # demo-user has an accepted plan on 2026-10-10
    python demo_seed.py --list         # show the scenarios and their suggested check-ins

Existing records.json / audit_log.json are moved into runtime_data/backups/<time>/ first;
nothing is deleted. Fictional user and simulated data only. The warning case needs no seed:
submit DEMO_CHECK_INS["warning"] after with_history.
"""
import argparse
import copy
import json
import os
import sys
from datetime import datetime

from contracts import make_result
import storage

DEMO_USER = "demo-user"
SCENARIOS = ("first_use", "with_history")

_BASE_CHECK_IN = {"user_id": DEMO_USER, "sitting_hours": 6.0, "pain_location": "Neck", "pain_score": 3,
                  "fatigue_score": 4, "warning_signs": []}

# Suggested inputs for the page, matching the three acceptance scenarios in B_DELIVERY.md.
DEMO_CHECK_INS = {
    "first_use": {**_BASE_CHECK_IN, "date": "2026-10-10", "previous_completion": "Not applicable"},
    "with_history": {**_BASE_CHECK_IN, "date": "2026-10-11", "previous_completion": "Partly completed",
                     "fatigue_score": 6},
    "warning": {**_BASE_CHECK_IN, "date": "2026-10-12", "previous_completion": "Completed",
                "warning_signs": ["Numbness"]},
}

_SOURCES = [
    {"id": "K01", "title": "Break up prolonged sitting",
     "content": "Standing up, changing position or moving for a few minutes at regular intervals "
                "(for example every 30-60 minutes) is a common recommendation for desk workers.",
     "url": "https://www.who.int/news-room/fact-sheets/detail/physical-activity"},
    {"id": "K02", "title": "Short walking breaks",
     "content": "A brief walk to refill water, use the stairs or talk to a colleague in person is an "
                "easy way to add movement.",
     "url": "https://www.who.int/news-room/fact-sheets/detail/physical-activity"},
]


def _plan(plan_id, advice):
    return {"plan_id": plan_id, "actions": [{
        "category": "break", "advice": advice,
        "reason": "Simulated demo record: 6 hours of sitting with neck discomfort.",
        "source_ids": ["K01", "K02"]}]}


def _record(record_id, day, decision, check_in, advice):
    return {
        "schema_version": 1, "record_id": record_id, "user_id": DEMO_USER, "date": day,
        "timestamp": f"{day}T09:05:00+08:00", "input": check_in, "plan": _plan(record_id, advice),
        "sources": copy.deepcopy(_SOURCES), "plan_status": decision, "decision": decision,
        "completion_feedback": None,
    }


def _history():
    rejected_input = {**_BASE_CHECK_IN, "date": "2026-10-09", "previous_completion": "Not applicable"}
    accepted_input = {**_BASE_CHECK_IN, "date": "2026-10-10", "previous_completion": "Not applicable"}
    records = [
        _record("demo-seed-2026-10-09", "2026-10-09", "rejected", rejected_input,
                "Stand up and change position at regular intervals."),
        _record("demo-seed-2026-10-10", "2026-10-10", "accepted", accepted_input,
                "Take a brief walk to add movement during the workday."),
    ]
    events = []
    for record in records:
        events.append({
            "event_id": f"decision:{record['record_id']}", "timestamp": record["timestamp"],
            "user_id": DEMO_USER, "record_id": record["record_id"], "input": record["input"],
            "action": "human_decision", "source_ids": ["K01", "K02"],
            "output": {"status": "saved", "message": "Simulated demo decision.", "trace": []},
            "human_decision": record["decision"]})
    return records, events


def reset_demo_data(scenario: str) -> dict:
    """Back up current data, then write the chosen scenario. Returns the shared result envelope."""
    if scenario not in SCENARIOS:
        return make_result("error", message=f"Unknown scenario; choose one of {', '.join(SCENARIOS)}.",
                           error_code="INVALID_INPUT")
    folder = storage.data_dir()
    backup = None
    try:
        with storage._lock:
            existing = [folder / n for n in (storage.RECORDS_FILE, storage.LOGS_FILE) if (folder / n).exists()]
            if existing:
                backup = folder / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                backup.mkdir(parents=True)
                for path in existing:
                    os.replace(path, backup / path.name)
            records, events = _history() if scenario == "with_history" else ([], [])
            for record in records:
                storage._check_record(record)
            for event in events:
                storage._check_event(event)
            storage._write(storage.RECORDS_FILE, "records", records)
            storage._write(storage.LOGS_FILE, "events", events)
    except (OSError, storage.StorageError):
        return make_result("error", message="Resetting demo data failed; existing files were not deleted.",
                           error_code="STORAGE_ERROR")
    return make_result("saved", message=f"Demo scenario '{scenario}' is ready.",
                       data={"scenario": scenario, "records": len(records), "events": len(events),
                             "backup": str(backup) if backup else None,
                             "suggested_check_in": copy.deepcopy(DEMO_CHECK_INS[scenario])},
                       trace=[{"step": "Reset demo data", "status": "completed", "tool": "Demo seeder"}])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reset WorkWell demo data (simulated only).")
    parser.add_argument("scenario", nargs="?", choices=SCENARIOS)
    parser.add_argument("--list", action="store_true", help="show scenarios and suggested check-ins")
    args = parser.parse_args(argv)
    if args.list or not args.scenario:
        print(json.dumps(DEMO_CHECK_INS, indent=2))
        return 0
    result = reset_demo_data(args.scenario)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "saved" else 1


if __name__ == "__main__":
    sys.exit(main())
