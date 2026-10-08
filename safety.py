"""Member B: input validation and safety rules."""
from contracts import make_result


def validate_input(check_in: dict) -> dict:
    return make_result("error", message="Input validation is not implemented yet.", error_code="NOT_IMPLEMENTED")


def check_safety(check_in: dict, history: list[dict]) -> dict:
    return make_result("error", message="Safety rules are not implemented yet.", error_code="NOT_IMPLEMENTED")


def validate_plan(plan: dict, sources: list[dict]) -> dict:
    return make_result("error", message="Plan safety validation is not implemented yet.", error_code="NOT_IMPLEMENTED")
