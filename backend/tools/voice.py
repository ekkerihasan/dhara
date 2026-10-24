"""Facts form by voice: a spoken description of the rental becomes the form's fields.

The transcript is redacted first. The model proposes values through one tool call; code keeps only
values in a sensible range and from the allowed lists, so the tenant reviews a form, not prose.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

from backend.llm.provider import ToolCallOrText
from backend.tools.agreement import redact_pii

LOGGER = logging.getLogger(__name__)
ProviderChat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], ToolCallOrText]

LOCAL_BODIES = ("municipal_corporation", "city_municipal_council", "other")
USES = ("residential", "non_residential")

SET_FACTS = {"type": "function", "function": {
    "name": "set_facts",
    "description": "Fill the rental facts the tenant mentioned. Leave out anything not said.",
    "parameters": {"type": "object", "properties": {
        "rent_per_month": {"type": "integer", "description": "Monthly rent in rupees"},
        "deposit_inr": {"type": "integer", "description": "Security deposit in rupees"},
        "built_year": {"type": "integer", "description": "Year the building was constructed"},
        "substantial_renovation_year": {"type": "integer"},
        "local_body": {"type": "string", "enum": list(LOCAL_BODIES),
                       "description": "municipal_corporation for Bengaluru (BBMP), Mysuru, Mangaluru and other city corporations; "
                                      "city_municipal_council for a CMC town; other if unclear"},
        "premises_use": {"type": "string", "enum": list(USES)},
    }}}}

PROMPT = ("The tenant described their rental out loud, in English, Kannada or Hindi. Call set_facts with only the facts they said. "
          "Convert spoken amounts to rupees: 'one and a half lakh' is 150000, 'twenty-five thousand' is 25000.")


def _clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep plausible values only; drop anything the form cannot use."""
    facts: dict[str, Any] = {}
    this_year = date.today().year
    for key, low, high in (("rent_per_month", 500, 10_000_000), ("deposit_inr", 0, 100_000_000)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and low <= value <= high:
            facts[key] = int(value)
    for key in ("built_year", "substantial_renovation_year"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and 1850 <= value <= this_year:
            facts[key] = int(value)
    if raw.get("local_body") in LOCAL_BODIES:
        facts["local_body"] = raw["local_body"]
    if raw.get("premises_use") in USES:
        facts["premises_use"] = raw["premises_use"]
    return facts


def facts_from_speech(transcript: str, chat: ProviderChat) -> dict[str, Any]:
    """Return {transcript (redacted), facts} from what the tenant said."""
    text, redactions = redact_pii(transcript)
    result = chat([{"role": "system", "content": PROMPT}, {"role": "user", "content": text}], [SET_FACTS])
    call = next((c for c in result.tool_calls if c.name == "set_facts"), None)
    facts = _clean(call.arguments) if call else {}
    LOGGER.info("facts_from_speech fields=%s redactions=%s", sorted(facts), sum(redactions.values()))
    return {"transcript": text, "facts": facts}
