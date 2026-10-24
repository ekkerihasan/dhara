"""Validate the data contract independently of the retrieval tool."""
import json
from pathlib import Path


def test_law_library_integrity() -> None:
    entries = json.loads((Path(__file__).parents[1] / "law/karnataka.json").read_text(encoding="utf-8"))
    assert len(entries) >= 20
    assert len({entry["id"] for entry in entries}) == len(entries)
    required = {"id", "act", "section", "title", "paraphrase", "source_url", "applies_in_karnataka", "notes"}
    for entry in entries:
        assert required <= entry.keys()
        assert entry["source_url"].startswith("https://")
        assert isinstance(entry["applies_in_karnataka"], bool)
        assert entry["paraphrase"] and entry["notes"]
    excluded = {entry["id"] for entry in entries if not entry["applies_in_karnataka"]}
    assert excluded == {"MTA-11(1)", "MTA-30"}
