"""Member C: source-grounded retrieval. data/knowledge.json is empty, not a completed knowledge base."""
from contracts import make_result


def retrieve_guidance(check_in: dict) -> dict:
    return make_result("error", message="Knowledge retrieval is not implemented yet.", error_code="NOT_IMPLEMENTED")
