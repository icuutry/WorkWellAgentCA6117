"""Member C: model calls. Add the chosen provider SDK dependency through a PR."""
from contracts import make_result


def generate_plan(check_in: dict, feedback_context: dict, sources: list[dict]) -> dict:
    return make_result("error", message="Model generation is not implemented yet.", error_code="NOT_IMPLEMENTED")
