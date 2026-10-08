"""Keyword/tag retrieval over knowledge.json (member C).

retrieve_guidance(input) -> {"status": "ok", "sources": [...], "message": str}
                         or {"status": "error", "error": code, "message": str}
An empty "sources" list means "no match" (status stays "ok"); B decides to stop.
"""
import json
from pathlib import Path

KNOWLEDGE_PATH = Path(__file__).with_name("knowledge.json")
MAX_SOURCES = 5

# discomfort area (lower-case substring) -> knowledge tags
AREA_TAGS = {
    "neck": ["neck", "shoulder", "monitor"],
    "shoulder": ["shoulder", "neck", "arm"],
    "upper back": ["upper_back", "back", "posture"],
    "lower back": ["lower_back", "back", "posture"],
    "back": ["back", "lower_back", "posture"],
    "wrist": ["wrist", "hand", "typing"],
    "hand": ["hand", "wrist", "typing"],
    "finger": ["hand", "wrist", "typing"],
    "arm": ["arm", "wrist", "shoulder"],
    "elbow": ["arm", "wrist"],
    "eye": ["eyes", "eye_strain", "screen"],
    "head": ["headache", "eyes", "screen"],
}


def load_knowledge(path=None):
    """Load the knowledge base. Raises ValueError on a missing/corrupt file."""
    try:
        with open(path or KNOWLEDGE_PATH, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load knowledge base: {exc}") from exc
    if not isinstance(items, list):
        raise ValueError("knowledge base must be a list")
    return items


def build_query_tags(inp):
    """Turn a self-assessment into a weighted tag list (tag -> weight)."""
    tags = {}

    def add(tag, w):
        tags[tag] = max(tags.get(tag, 0), w)

    area = str(inp.get("discomfort_area") or "").lower()
    try:
        score = float(inp.get("discomfort_score") or 0)
    except (TypeError, ValueError):
        score = 0
    if area and score > 0:
        for key, area_tags in AREA_TAGS.items():
            if key in area:
                for i, t in enumerate(area_tags):
                    add(t, 3 if i == 0 else 2)
                break
        if score >= 4:
            add("stretching", 1)
    try:
        if float(inp.get("sitting_hours") or 0) >= 4:
            for t in ("sedentary", "sitting", "micro_break", "movement"):
                add(t, 2)
    except (TypeError, ValueError):
        pass
    try:
        if float(inp.get("fatigue_score") or 0) >= 5:
            for t in ("fatigue", "recovery"):
                add(t, 2)
            add("stress", 1)
    except (TypeError, ValueError):
        pass
    return tags


def retrieve_guidance(inp, max_results=MAX_SOURCES, knowledge=None):
    try:
        items = knowledge if knowledge is not None else load_knowledge()
    except ValueError as exc:
        return {"status": "error", "error": "knowledge_unavailable", "message": str(exc)}

    query = build_query_tags(inp)
    scored = []
    for item in items:
        score = sum(query.get(t, 0) for t in item.get("tags", []))
        if score > 0:
            scored.append((score, item["id"], item))
    scored.sort(key=lambda x: (-x[0], x[1]))
    sources = [dict(item, score=score) for score, _, item in scored[:max_results]]
    msg = f"{len(sources)} source(s) found" if sources else "no matching guidance found"
    return {"status": "ok", "sources": sources, "message": msg, "query_tags": sorted(query)}
