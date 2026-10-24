"""Scripted landlord for the pre-signing negotiation. No model: a move table per task and persona.

Each clause has two moves per persona, [opening, concession], in env/tasks/<task>.json under
landlord_moves. A move's `acceptable` flag is the answer key for the scorer and is never sent to
the tenant agent. The rules that set it live here too, so the data can be checked against them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.models import Decision, Offer, TenantLimits
from backend.tools.agreement import read_agreement

TASKS_DIR = Path(__file__).resolve().parents[2] / "env" / "tasks"
NEGOTIATION_TASKS = ("blr_flat", "pg_room")
PERSONA_LABELS = {"strict_owner": "Strict owner", "reasonable_broker": "Reasonable broker"}


def load_task(name: str) -> dict[str, Any]:
    return json.loads((TASKS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def task_for_clauses(clauses: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The scripted landlord only knows the demo agreements: match the clause texts exactly."""
    texts = [(clause["id"], clause["text"].strip()) for clause in clauses]
    for name in NEGOTIATION_TASKS:
        task = load_task(name)
        if [(c["id"], c["text"].strip()) for c in read_agreement(task["agreement_text"])["clauses"]] == texts:
            return task
    return None


def _offer(clause_id: str, move: dict[str, Any]) -> Offer:
    """Strip the hidden `acceptable` flag."""
    return Offer(clause_id=clause_id, move_id=move["move_id"], text=move["text"], terms=dict(move["terms"]))


def opening(task: dict[str, Any], persona: str, clause_ids: list[str]) -> list[Offer]:
    """The first move per clause, in the order given."""
    moves = task.get("landlord_moves", {})
    return [_offer(clause_id, moves[clause_id][persona][0]) for clause_id in clause_ids if clause_id in moves]


def respond(task: dict[str, Any], persona: str, previous: list[Decision]) -> list[Offer]:
    """Concede on clauses the tenant rejected or countered; repeat the opening for accepted ones."""
    moves = task.get("landlord_moves", {})
    return [_offer(d.clause_id, moves[d.clause_id][persona][0 if d.decision == "accept" else 1])
            for d in previous if d.clause_id in moves]


def is_acceptable(move_id: str, task: dict[str, Any]) -> bool | None:
    """The answer key: the stored flag for a move, or None if the move is unknown."""
    for personas in task.get("landlord_moves", {}).values():
        for moves in personas.values():
            for move in moves:
                if move["move_id"] == move_id:
                    return bool(move["acceptable"])
    return None


def limit_breach(terms: dict[str, Any], limits: TenantLimits) -> str | None:
    """The first TenantLimits field these terms exceed, or None. Only the tenant's own three limits."""
    checks = (("lock_in_months", "max_lock_in_months"), ("refund_within_days", "refund_within_days"),
              ("painting_inr", "max_exit_painting_inr"))
    for term, field in checks:
        if term in terms and terms[term] > getattr(limits, field):
            return field
    return None


def within_limits(terms: dict[str, Any], limits: TenantLimits) -> bool:
    """The tenant's limits plus the fairness rules of section 3: no forfeiture on any breach,
    symmetric notice of at most 2 months, and at least 24 hours' notice before entry."""
    if limit_breach(terms, limits):
        return False
    if terms.get("forfeit_on_any_breach"):
        return False
    if "tenant_notice_months" in terms:
        tenant, landlord = terms["tenant_notice_months"], terms.get("landlord_notice_months")
        if tenant != landlord or tenant > 2:
            return False
    if "notice_hours" in terms and terms["notice_hours"] < 24:
        return False
    return True
