"""Shared helper for parsing JSON out of a model's text response, since
models often wrap JSON in markdown code fences despite being asked not
to."""
import json
import re

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(text: str) -> dict:
    cleaned = _CODE_FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response was not valid JSON: {exc}") from exc
