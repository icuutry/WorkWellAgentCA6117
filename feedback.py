"""Member D: turn history and current completion feedback into model context."""
from contracts import make_result


def build_feedback_context(check_in: dict, history: list[dict]) -> dict:
    return make_result("error", message="Feedback context is not implemented yet.", error_code="NOT_IMPLEMENTED")
