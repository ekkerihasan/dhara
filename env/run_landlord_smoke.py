"""Live, synthetic landlord negotiation smoke test; writes no credentials."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backend.agent.landlord import (NegotiationMessage, NegotiationRequest, advance_landlord,
    new_negotiation, prepare_message)
from backend.llm.provider import ProviderError, ToolCallOrText, chat


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("groq", "sarvam"))
    args = parser.parse_args()
    provider = args.provider or os.getenv("MODEL_PROVIDER", "groq").strip().casefold()
    if provider not in {"groq", "sarvam"}:
        parser.error("MODEL_PROVIDER must be groq or sarvam")
    os.environ["MODEL_PROVIDER"] = provider
    request = NegotiationRequest(task_id="pg_room", approved=True, language="en", tenant_message=(
        "Please replace blanket full-deposit forfeiture with documented reasonable loss. "
        "For the INR 3000 cleaning charge, please provide an itemised invoice."))
    provider_calls: list[dict[str, Any]] = []

    def recorded_chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ToolCallOrText:
        try:
            response = chat(messages, tools)
        except ProviderError as exc:
            # ProviderError is the provider boundary's credential-free error type.
            provider_calls.append({"error": str(exc)})
            raise
        provider_calls.append({"tools_returned": [call.name for call in response.tool_calls],
                               "free_text_present": bool(response.text)})
        return response

    state = new_negotiation("synthetic-pg-smoke", request, recorded_chat)
    result = advance_landlord(state)
    if result.status == "ready":
        prepare_message(state, NegotiationMessage(approved=True, tenant_message=(
            "I can agree to the INR 3000 cleaning charge supported by an itemised invoice, "
            "with other deposit deductions based on documented reasonable loss. Please confirm this wording.")))
        result = advance_landlord(state)
    artifact = {"date": datetime.now(timezone.utc).isoformat(), "provider": provider,
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b") if provider == "groq" else os.getenv("SARVAM_MODEL", "sarvam-105b"), "task_id": "pg_room",
        "synthetic": True, "simulated": True, "delivery_status": "not_sent", "status": result.status,
        "turns": result.turns, "error": result.error,
        "provider_calls": provider_calls,
        "verifier_events": [step.data for step in result.trace if step.type == "verifier"]}
    target = root / "env/results/landlord_smoke.json"
    target.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    target.with_name(f"landlord_smoke_{provider}.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.status, "model": artifact["model"], "turns": len(result.turns),
                      "artifact": str(target.relative_to(root))}))
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
