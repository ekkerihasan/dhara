"""Score the plain model (baseline) against the full Dhara agent on each Flow 1 task.

Both get the same agreement, the same categories and the same law pack. The baseline has no tools
and no verifier, so it must decide the governing law and every rupee amount itself, and all of its
claims count. The agent is scored on what reaches the tenant: its findings and the claims the
verifier let through. Writes env/results/scores.json and env/results/scores.md.

    python -m env.run_eval
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable

from backend.agent.tenant import MONEY_INPUTS, AgentState, ProviderChat, _law_index, start_agent
from backend.llm.provider import ProviderError, chat
from backend.tools.agreement import read_agreement
from env.scorer import score

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("blr_flat", "pg_room")  # moveout is Flow 2 and is scored by its own agent
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
    messages = [
        {"role": "system", "content": BASELINE_PROMPT.format(money=MONEY_INPUTS, law=_law_index())},
        {"role": "user", "content": json.dumps({"clauses": read_agreement(task["agreement_text"])["clauses"], "facts": task["facts"]}, ensure_ascii=False)},
    ]
    reply = _json_object(model(messages, []).text or "")
    findings = []
    for f in reply.get("findings", []):
        try:
            findings.append({"clause_ref": str(f["clause_ref"]), "category": str(f["category"]),
                             "money_at_risk_inr": int(round(float(f["money_at_risk_inr"]))), "section_ids": [str(s) for s in f.get("section_ids", [])]})
        except (KeyError, TypeError, ValueError):
            continue  # a malformed finding earns nothing, as with any wrong answer
    claims = [{"text": str(c.get("text", "")), "section_id": c.get("section_id")} for c in reply.get("claims", []) if isinstance(c, dict)]
    return {"governing_law": str(reply.get("governing_law", "")), "findings": findings, "claims": claims}


def agent_run(task: dict[str, Any], model: ProviderChat) -> dict[str, Any]:
    """The full agent; a fact the task leaves blank is answered "I don't know"."""
    state = AgentState(task["id"], read_agreement(task["agreement_text"])["clauses"], dict(task["facts"]), task.get("language", "en"), model)
    response = start_agent(state)
    if response.status == "needs_input":
        state.unknown_facts.update(key for key, value in task["facts"].items() if value is None)
        response = start_agent(state)
    reached_tenant = [{"text": v["text"], "section_id": v["section_id"]} for v in response.verdicts if v["verdict"] != "blocked"]
    return {"governing_law": governing_label(state.rent_act_applies),
            "findings": [f.model_dump(include={"clause_ref", "category", "money_at_risk_inr", "section_ids"}) for f in response.findings],
            "claims": reached_tenant, "tool_calls": state.tool_calls, "status": response.status}


def evaluate(model: ProviderChat = chat, tasks: tuple[str, ...] = TASKS) -> dict[str, Any]:
    rows = []
    for name in tasks:
        task = json.loads((ROOT / "env" / "tasks" / f"{name}.json").read_text(encoding="utf-8"))
        for mode, runner in (("baseline", baseline_run), ("agent", agent_run)):
            try:
                run = runner(task, model)
                result = score(task, run)
                error = None
            except (ProviderError, ValueError) as exc:
                run, result, error = {}, {"total": 0.0}, str(exc)
            rows.append({"task": name, "mode": mode, "score": result, "error": error,
                         "findings": len(run.get("findings", [])), "governing_law": run.get("governing_law")})
    return {"date": date.today().isoformat(), "rows": rows}


def markdown(results: dict[str, Any], model_name: str) -> str:
    lines = [f"# Baseline vs agent ({results['date']}, {model_name})", "",
             "Same model, same agreement, same law pack. The baseline has no tools and no verifier. One run each; scores are out of 3.", "",
             "| Task | Mode | Governing law | Money within Rs 500 | Citations exist | Wrong-law penalty | Total |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in results["rows"]:
        s = row["score"]
        if row["error"]:
            lines.append(f"| {row['task']} | {row['mode']} | error: {row['error'][:60]} | | | | 0 |")
            continue
        lines.append(f"| {row['task']} | {row['mode']} | {s['governing_law_correct']} | {s['money_within_500']:.2f} | "
                     f"{s['citations_exist']:.2f} | {s['wrong_law_penalty']} | **{s['total']:.2f}** |")
    return "\n".join(lines) + "\n"


def main() -> None:
    import os
    results = evaluate()
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "scores.json").write_text(json.dumps({**results, "model": model_name}, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "scores.md").write_text(markdown(results, model_name), encoding="utf-8")
    print(markdown(results, model_name))


if __name__ == "__main__":
    main()
