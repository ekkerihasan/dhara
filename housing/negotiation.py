"""Conservative offline negotiation over public preference review results."""
from __future__ import annotations

import re

from .review import review_document
from .messages import draft_messages


_RULES = {
    "max_deposit_months": ("deposit", r"(\d+(?:\.\d+)?)\s*months?"),
    "max_notice_days": ("notice", r"(\d+(?:\.\d+)?)\s*days?"),
    "min_notice_days": ("notice", r"(\d+(?:\.\d+)?)\s*days?"),
    "max_rent_increase_percent": ("increase", r"(\d+(?:\.\d+)?)\s*%"),
    "max_refund_days": ("refund", r"(\d+(?:\.\d+)?)\s*days?"),
    "min_entry_notice_hours": ("entry", r"(\d+(?:\.\d+)?)\s*hours?"),
}


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def negotiate(review: dict, clause_id: str, offer: str, history: list | None = None) -> dict:
    """Assess at most three offers per clause; ambiguity always needs clarification.

    History is returned as a new list and never mutates caller-owned entries.
    Acceptance means only that supported numeric preferences were satisfied.
    It does not establish legal validity or approve the complete agreement.
    """
    entries = [dict(item) for item in (history or [])]
    relevant = [item for item in entries if item.get("clause_id") == clause_id]

    def result(decision, status, reason, revision="", *, append=True):
        if append:
            entries.append({"clause_id": clause_id, "offer": offer,
                            "decision": decision, "status": status,
                            "reason": reason, "proposed_revision": revision})
        agreements = {}
        for entry in entries:
            if entry.get("decision") == "accept":
                agreements.setdefault(entry["clause_id"], {"clause_id": entry["clause_id"], "text": entry["offer"]})
        unresolved = [finding for finding in review.get("findings", [])
                      if finding.get("clause_id") not in agreements]
        return {"decision": decision, "status": status, "reason": reason,
                "proposed_revision": revision, "history": entries,
                "messages": draft_messages(unresolved, list(agreements.values()))}

    accepted = next((item for item in relevant if item.get("decision") == "accept"), None)
    if accepted:
        return result("accept", "accepted", "This clause already has an agreed offer.",
                      accepted["offer"], append=False)
    if len(relevant) >= 3:
        return result("escalate", "limit_reached", "Three offers exhausted; ask a human to resolve this clause.", append=False)
    if isinstance(offer, str) and any(_normalize(item.get("offer", "")) == _normalize(offer) for item in relevant):
        return result("escalate", "duplicate_offer", "This offer repeats a previous proposal; human review is needed.")

    clause = next((item for item in review.get("clauses", []) if item["id"] == clause_id), None)
    if clause is None:
        return result("clarify", "unknown_clause", "Choose an extracted clause before negotiating.")
    findings = [item for item in review.get("findings", []) if item.get("clause_id") == clause_id]
    if any(item.get("category") in {"legal", "legal_conflict", "legal_violation", "potential_legal_conflict"} for item in findings):
        return result("escalate", "human_review", "A legal finding requires qualified human review.")
    if not isinstance(offer, str) or not offer.strip():
        return result("clarify", "missing_offer", "Provide the proposed clause text.")
    if not findings:
        return result("clarify", "no_review_target", "No reviewed conflict identifies what this offer must resolve.")
    preferences = review.get("preferences", {})
    rules = {item.get("rule") for item in findings if item.get("rule") in _RULES}
    # Compatibility with older public reviews: infer relevant configured rules
    # from the original clause, never from private environment answers.
    original = clause["text"].casefold()
    original_rules = {key for key, (keyword, _) in _RULES.items()
                      if key in preferences and keyword in original}
    if re.search(r"\b(entry|access|inspection|enter)\b", original) and not re.search(r"\b(terminat\w*|vacat\w*|evict\w*)\b", original):
        original_rules -= {"max_notice_days", "min_notice_days"}
    rules |= original_rules
    if not rules or any(not item.get("rule") for item in findings if item.get("category") == "ambiguity"):
        return result("clarify", "unresolved_ambiguity", "The original ambiguity needs explicit human clarification before acceptance.")

    for rule in rules:
        if rule not in preferences:
            return result("clarify", "missing_preference", "Confirm the numeric preference before comparing offers.")
        keyword, pattern = _RULES[rule]
        lowered = offer.casefold()
        # Require one comparable numeric value in a relevant sentence. This
        # prevents disappearance of a term from masquerading as resolution.
        sentences = [s for s in re.split(r"(?<=[.;])\s+", lowered) if keyword in s]
        if rule in {"max_notice_days", "min_notice_days"}:
            sentences = [s for s in sentences if not re.search(r"\b(entry|access|inspection|enter)\b", s)]
        values = re.findall(pattern, " ".join(sentences))
        if len(values) != 1:
            return result("clarify", "incomplete_offer", f"State one explicit comparable value for {rule}.")

    offer_review = review_document(offer, state=review.get("state", ""), preferences=preferences,
                                   facts=review.get("jurisdiction", {}).get("facts", {}))
    if any(item["category"] in {"legal", "legal_conflict", "legal_violation", "potential_legal_conflict"} for item in offer_review["findings"]):
        return result("escalate", "human_review", "The proposed wording raises a legal finding requiring human review.")
    if any(item["category"] == "ambiguity" for item in offer_review["findings"]):
        return result("clarify", "ambiguous_offer", "The proposed wording still needs clarification.")
    conflicts = [item for item in offer_review["findings"] if item["category"] == "preference"]
    if conflicts:
        proposal = " ".join(dict.fromkeys(item["proposed_revision"] for item in conflicts))
        return result("counter", "counter_proposed", "The offer still conflicts with the stated numeric preferences.", proposal)
    return result("accept", "accepted", "Supported numeric preferences are satisfied; legal applicability remains unverified.", offer)
