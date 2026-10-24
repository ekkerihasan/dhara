"""The frontend stubs must cite only sections that exist in the law pack, with the same metadata."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAW = {e["id"]: e for e in json.loads((ROOT / "law" / "karnataka.json").read_text(encoding="utf-8"))}
STUBS = sorted((ROOT / "frontend" / "stubs").glob("*.json"))
FIELDS = ("act", "section", "title", "source_url", "applies_in_karnataka")


def test_stubs_exist() -> None:
    assert {p.name for p in STUBS} >= {"blr_flat.json", "moveout.json"}


def test_stub_sections_match_law_pack() -> None:
    for path in STUBS:
        sections = json.loads(path.read_text(encoding="utf-8"))["sections"]
        for section_id, section in sections.items():
            assert section_id in LAW, f"{path.name}: {section_id} is not in law/karnataka.json"
            for field in FIELDS:
                assert section[field] == LAW[section_id][field], f"{path.name}: {section_id}.{field} differs"


def test_blocked_claims_cite_inapplicable_law_or_nothing() -> None:
    run = json.loads((ROOT / "frontend" / "stubs" / "blr_flat.json").read_text(encoding="utf-8"))
    blocked = [s for s in run["trace"] if s["type"] == "verifier" and s["verdict"] == "blocked"]
    assert blocked
    for step in blocked:
        assert step["section_id"] is None or LAW[step["section_id"]]["applies_in_karnataka"] is False
