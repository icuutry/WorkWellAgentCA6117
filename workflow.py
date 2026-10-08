"""Member B: workflow and human decisions. Placeholders do not pretend to implement the actual workflow."""
from contracts import make_result


def start_workflow(check_in: dict) -> dict:
    # TODO B: safety checks -> D memory/feedback -> C retrieval/model -> output checks -> save draft/logs.
    return make_result("error", message="Member B's workflow is not implemented yet.",
                       error_code="NOT_IMPLEMENTED")


def submit_decision(record: dict) -> dict:
    # TODO B: validate the draft and decision, then use D to save records and audit events idempotently.
    return make_result("error", message="Decision handling is not implemented yet.",
                       error_code="NOT_IMPLEMENTED")
