"""Score the plain model (baseline) against the full Dhara agent on each task.

Both get the same agreement, the same categories and the same law pack. The baseline has no tools
and no verifier, so it must decide the governing law and every rupee amount itself, and all of its
claims count. The agent is scored on what reaches the tenant: its findings and the claims the
verifier let through. On tasks with a scripted landlord both then negotiate two rounds against the
strict owner with the same offers and model; the baseline has no limits enforcement, no verifier and
no rule fallback. Writes env/results/scores.json and env/results/scores.md.

    python -m env.run_eval
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from backend.agent.moveout import MoveoutState, start_moveout
from backend.agent.negotiation import negotiate
from backend.agent.tenant import MONEY_INPUTS, AgentState, ProviderChat, _law_index, start_agent
from backend.llm.provider import ProviderError, chat
from backend.tools.agreement import read_agreement
from env.scorer import score

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("blr_flat", "pg_room", "moveout")  # moveout is Flow 2: claimed deductions against the move-in checklist
RESULTS = ROOT / "env" / "results"

BASELINE_PROMPT = """You review a residential rental agreement in Karnataka for the tenant. You have no tools.
Reply with ONLY a JSON object:
{{"governing_law": "TPA_CONTRACT" if the Karnataka Rent Act does not apply, "KARNATAKA_RENT_ACT" if it applies, "UNRESOLVED" if facts are missing,
  "findings": [{{"clause_ref": "C2", "category": one of deposit_forfeiture, lock_in, painting_or_cleaning_fixed, notice_shortfall, rent_escalation_excess,
                "money_at_risk_inr": integer rupees, "section_ids": [section ids]}}],
  "claims": [{{"text": "a legal claim", "section_id": "a section id or null"}}]}}
Money at risk by category: {money} Escalation counts only above 10 percent a year: (percent - 10) percent of annual rent.
Section ids you may cite:
{law}"""


MOVEOUT_BASELINE_PROMPT = """You check a landlord's move-out deductions for a tenant in Karnataka. You have no tools.
Reply with ONLY a JSON object:
{{"governing_law": "TPA_CONTRACT" if the Karnataka Rent Act does not apply, "KARNATAKA_RENT_ACT" if it applies, "UNRESOLVED" if facts are missing,
  "findings": [one per claimed deduction: {{"clause_ref": its clause_ref, "category": its category, "money_at_risk_inr": the claimed amount,
                "verdict": "allowed" or "disputed", "section_ids": [section ids]}}],
  "claims": [{{"text": "a legal claim", "section_id": "a section id or null"}}]}}
Section ids you may cite:
{law}"""


def governing_label(applies: bool | None) -> str:
    """The scorer's labels for the Rent Act result."""
    return {False: "TPA_CONTRACT", True: "KARNATAKA_RENT_ACT", None: "UNRESOLVED"}[applies]


def _json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("Baseline reply had no JSON object")
    return json.loads(match.group(0))


def baseline_run(task: dict[str, Any], model: ProviderChat) -> dict[str, Any]:
    """One plain model call, parsed into the scorer's run shape."""
    clauses = read_agreement(task["agreement_text"])["clauses"]
    if "claimed_deductions" in task:
        prompt = MOVEOUT_BASELINE_PROMPT.format(law=_law_index())
        payload = {"clauses": clauses, "facts": task["facts"], "move_in_checklist": task["move_in_checklist"],
                   "claimed_deductions": [{k: v for k, v in d.items() if k != "expected_verdict"} for d in task["claimed_deductions"]]}
    else:
        prompt = BASELINE_PROMPT.format(money=MONEY_INPUTS, law=_law_index())
        payload = {"clauses": clauses, "facts": task["facts"]}
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    reply = _json_object(model(messages, []).text or "")
    findings = []
    for f in reply.get("findings", []):
        try:
            findings.append({"clause_ref": str(f["clause_ref"]), "category": str(f["category"]),
                             "money_at_risk_inr": int(round(float(f["money_at_risk_inr"]))), "section_ids": [str(s) for s in f.get("section_ids", [])]})
        except (KeyError, TypeError, ValueError):
            continue  # a malformed finding earns nothing, as with any wrong answer
    claims = [{"text": str(c.get("text", "")), "section_id": c.get("section_id")} for c in reply.get("claims", []) if isinstance(c, dict)]
    run = {"governing_law": str(reply.get("governing_law", "")), "findings": findings, "claims": claims}
    if task.get("landlord_moves"):
        applies = {"TPA_CONTRACT": False, "KARNATAKA_RENT_ACT": True}.get(run["governing_law"])
        state = AgentState(task["id"], clauses, dict(task["facts"]), task.get("language", "en"), model)
        run["negotiation"] = negotiate(state, task, findings, applies, enforce=False).model_dump()
        run["negotiation_errors"] = negotiation_errors(state)
    return run


def moveout_run(task: dict[str, Any], model: ProviderChat) -> dict[str, Any]:
    """The Flow 2 agent: every claimed deduction becomes a finding at its claimed amount."""
    deductions = [{"id": f"D{i}", **{k: v for k, v in d.items() if k != "expected_verdict"}} for i, d in enumerate(task["claimed_deductions"], start=1)]
    state = MoveoutState(task["id"], read_agreement(task["agreement_text"])["clauses"], task["move_in_checklist"], deductions,
                         dict(task["facts"]), task.get("language", "en"), model)
    response = start_moveout(state)
    findings = [{"clause_ref": d["clause_ref"], "category": d["category"], "money_at_risk_inr": d["amount_inr"],
                 "section_ids": d.get("section_ids", [])} for d in response["deductions"]]
    return {"governing_law": governing_label(state.rent_act_applies), "findings": findings, "claims": [], "status": response["status"]}


def negotiation_errors(state: AgentState) -> list[str]:
    """Why a round fell back to rules (rate limit, tool budget, malformed call), from the trace."""
    return [str(s.data["error"]) for s in state.trace if s.type == "tenant_decision" and s.data.get("error")]


def agent_run(task: dict[str, Any], model: ProviderChat) -> dict[str, Any]:
    """The full agent; a fact the task leaves blank is answered "I don't know"."""
    if "claimed_deductions" in task:
        return moveout_run(task, model)
    state = AgentState(task["id"], read_agreement(task["agreement_text"])["clauses"], dict(task["facts"]), task.get("language", "en"), model)
    response = start_agent(state)
    if response.status == "needs_input":
        state.unknown_facts.update(key for key, value in task["facts"].items() if value is None)
        response = start_agent(state)
    reached_tenant = [{"text": v["text"], "section_id": v["section_id"]} for v in response.verdicts if v["verdict"] != "blocked"]
    return {"governing_law": governing_label(state.rent_act_applies),
            "findings": [f.model_dump(include={"clause_ref", "category", "money_at_risk_inr", "section_ids"}) for f in response.findings],
            "claims": reached_tenant, "tool_calls": state.tool_calls, "status": response.status,
            "negotiation": response.negotiation.model_dump() if response.negotiation else None,
            "negotiation_errors": negotiation_errors(state)}


def evaluate(model: ProviderChat = chat, tasks: tuple[str, ...] = TASKS, pause_s: float = 0.0) -> dict[str, Any]:
    """pause_s spaces the runs out, so a free-tier rate limit does not decide the score."""
    rows = []
    requests = failures = 0

    def measured_model(messages: list[dict[str, Any]], tools: list[dict[str, Any]]):
        nonlocal requests, failures
        requests += 1
        try:
            return model(messages, tools)
        except ProviderError:
            failures += 1
            raise

    for name in tasks:
        task = json.loads((ROOT / "env" / "tasks" / f"{name}.json").read_text(encoding="utf-8"))
        for mode, runner in (("baseline", baseline_run), ("agent", agent_run)):
            if rows and pause_s:
                time.sleep(pause_s)
            failures_before = failures
            try:
                run = runner(task, measured_model)
                result = score(task, run)
                error = None
                if failures > failures_before:
                    error = "Provider failed; fallback output is not a live-model evaluation"
                elif run.get("status", "ready") != "ready":
                    error = "Agent did not complete a ready review"
            except (ProviderError, ValueError) as exc:
                run, result, error = {}, {"total": 0.0}, str(exc)
            rows.append({"task": name, "mode": mode, "score": result, "error": error,
                         "findings": len(run.get("findings", [])), "governing_law": run.get("governing_law"),
                         "tool_calls": run.get("tool_calls"), "negotiation": run.get("negotiation"),
                         "negotiation_errors": run.get("negotiation_errors", [])})
    return {"date": date.today().isoformat(), "rows": rows,
            "model_requests": requests, "provider_failures": failures}


def markdown(results: dict[str, Any], model_name: str) -> str:
    lines = [f"# Baseline vs agent ({results['date']}, {model_name})", "",
             "Same model, same agreement, same law pack. The baseline has no tools and no verifier. One run each; scores are out of 4 "
             "on the two pre-signing tasks (two negotiation rounds against the strict owner) and out of 3 on moveout.", "",
             "| Task | Mode | Governing law | Money within Rs 500 | Citations exist | Negotiation correct | Wrong-law penalty | Total |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in results["rows"]:
        s = row["score"]
        if row["error"]:
            lines.append(f"| {row['task']} | {row['mode']} | error: {row['error'][:60]} | | | | | 0 |")
            continue
        negotiation = "n/a" if s.get("negotiation_correct") is None else f"{s['negotiation_correct']:.2f}"
        lines.append(f"| {row['task']} | {row['mode']} | {s['governing_law_correct']} | {s['money_within_500']:.2f} | "
                     f"{s['citations_exist']:.2f} | {negotiation} | {s['wrong_law_penalty']} | **{s['total']:.2f}** |")
    return "\n".join(lines) + "\n"


def main() -> None:
    import os
    results = evaluate(pause_s=float(os.getenv("EVAL_PAUSE_S", "60")))
    provider = os.getenv("MODEL_PROVIDER", "groq").strip().casefold()
    model_name = (os.getenv("SARVAM_MODEL", "sarvam-105b") if provider == "sarvam"
                  else os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    if any(row["error"] for row in results["rows"]):
        (RESULTS / "last_failed_attempt.json").write_text(
            json.dumps({**results, "model": model_name, "provider": provider}, indent=2) + "\n", encoding="utf-8")
        raise SystemExit("Evaluation incomplete; previous scores preserved. See env/results/last_failed_attempt.json.")
    (RESULTS / "scores.json").write_text(json.dumps({**results, "model": model_name, "provider": provider}, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "scores.md").write_text(markdown(results, model_name), encoding="utf-8")
    print(markdown(results, model_name))


if __name__ == "__main__":
    main()
