"""Member C: source-grounded retrieval over data/knowledge.json.

retrieve_guidance(check_in) -> make_result("ok", data={"sources": [...]})
No match is still "ok" with an empty list; B converts that to NO_SOURCES (INTERFACES.md section 2).
Each source has id/title/content/url (contract) plus source_name/category/tags/score (extras).
Entries with category "reference_only" (warning-sign background) are never returned as plan sources.
"""
import json
from pathlib import Path

from contracts import is_english_content, make_result

KNOWLEDGE_PATH = Path(__file__).with_name("data") / "knowledge.json"
MAX_SOURCES = 5

# contracts.PAIN_LOCATIONS -> knowledge tags (first tag weighs most)
LOCATION_TAGS = {
    "Neck": ["neck", "shoulder", "monitor"],
    "Shoulders": ["shoulder", "neck", "arm"],
    "Lower back": ["lower_back", "back", "posture"],
    "Wrists": ["wrist", "hand", "typing"],
    "Eyes": ["eyes", "eye_strain", "screen"],
}


def load_knowledge(path=None):
    """Raises ValueError for a missing, corrupt or malformed knowledge file."""
    try:
        with open(path or KNOWLEDGE_PATH, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load knowledge base: {exc}") from exc
    if not isinstance(items, list):
        raise ValueError("knowledge base must be a list")
    for it in items:
        if not isinstance(it, dict) or not all(isinstance(it.get(k), str) and it[k] for k in ("id", "title", "content", "url")):
            raise ValueError("knowledge entry needs non-empty id/title/content/url")
        if any(not is_english_content(it[k]) for k in ("title", "content")):
            raise ValueError("Knowledge titles and content must be English")
        if "source_name" in it and not is_english_content(it["source_name"]):
            raise ValueError("Source names must be English")
    return items


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def build_query_tags(check_in):
    """Weighted tags (tag -> weight) derived from the check-in fields in INTERFACES.md."""
    tags = {}

    def add(tag, weight):
        tags[tag] = max(tags.get(tag, 0), weight)

    if _num(check_in.get("pain_score")) > 0:
        for i, t in enumerate(LOCATION_TAGS.get(check_in.get("pain_location"), [])):
            add(t, 3 if i == 0 else 2)
        if _num(check_in.get("pain_score")) >= 4:
            add("stretching", 1)
    if _num(check_in.get("sitting_hours")) >= 4:
        for t in ("sedentary", "sitting", "micro_break", "movement"):
            add(t, 2)
    if _num(check_in.get("fatigue_score")) >= 5:
        for t in ("fatigue", "recovery"):
            add(t, 2)
        add("stress", 1)
    if check_in.get("previous_completion") in ("Partly completed", "Not completed"):
        add("micro_break", 2)  # earlier plan was too hard: favour short, easy breaks
    return tags


def retrieve_guidance(check_in, max_results=MAX_SOURCES, knowledge=None):
    if not isinstance(check_in, dict):
        return make_result("error", message="Check-in must be a dictionary.", error_code="INVALID_INPUT")
    try:
        items = knowledge if knowledge is not None else load_knowledge()
    except ValueError as exc:
        return make_result("error", message=f"Knowledge base unavailable: {exc}", error_code="STORAGE_ERROR")

    if not isinstance(items, list) or any(not isinstance(item, dict) or any(
            not is_english_content(item.get(field)) for field in ("title", "content")) for item in items):
        return make_result("error", message="Knowledge titles and content must be English.", error_code="INVALID_MODEL_OUTPUT")
    if any("source_name" in item and not is_english_content(item["source_name"]) for item in items):
        return make_result("error", message="Source names must be English.", error_code="INVALID_MODEL_OUTPUT")
    query = build_query_tags(check_in)
    scored = []
    for item in items:
        if item.get("category") == "reference_only":
            continue
        score = sum(query.get(t, 0) for t in item.get("tags", []))
        if score > 0:
            scored.append((-score, item["id"], dict(item, score=score)))
    scored.sort(key=lambda x: (x[0], x[1]))
    sources = [s for _, _, s in scored[:max_results]]
    return make_result(
        "ok", data={"sources": sources},
        message=f"{len(sources)} source(s) found" if sources else "No matching guidance found.",
        trace=[{"step": "retrieve_guidance", "status": "ok", "tool": "keyword/tag retrieval",
                "detail": f"query tags: {sorted(query)}; source ids: {[s['id'] for s in sources]}"}],
    )
