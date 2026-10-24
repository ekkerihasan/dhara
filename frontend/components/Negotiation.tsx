import { Bot, Lock, Store } from "lucide-react";
import { inr } from "@/lib/format";
import type { Decision, Finding, LandlordPersona, Negotiation as NegotiationData, Section, Terms } from "@/lib/types";
import { SectionChip } from "./SectionChip";
import { VerdictBadge } from "./VerdictBadge";

export const PERSONA_LABEL: Record<LandlordPersona, string> = {
  strict_owner: "Strict owner",
  reasonable_broker: "Reasonable broker",
};

const KNOWN_TERMS = ["lock_in_months", "refund_within_days", "forfeit_on_any_breach", "painting_inr", "tenant_notice_months", "landlord_notice_months", "notice_hours", "ask"];

const STATUS: Record<NegotiationData["status"], { label: string; className: string }> = {
  running: { label: "Negotiating", className: "badge-amber" },
  settled: { label: "Settled", className: "badge-green" },
  stalled: { label: "Stalled", className: "badge-red" },
};

const DECISION: Record<Decision["decision"], string> = { accept: "badge-green", reject: "badge-red", counter: "badge-amber" };

/** "Lock-in", "Exit painting"... from the term keys the scripted landlord uses. */
function clauseTopic(terms: Terms): string {
  if ("lock_in_months" in terms) return "Lock-in";
  if ("refund_within_days" in terms) return "Deposit refund";
  if ("painting_inr" in terms) return "Exit painting or cleaning";
  if ("tenant_notice_months" in terms) return "Notice period";
  if ("notice_hours" in terms) return "Landlord entry";
  return "Clause";
}

/** Terms in words: {"lock_in_months": 4} -> "4-month lock-in". The standing ask is shown separately. */
export function termsText(terms: Terms): string {
  const parts: string[] = [];
  if (typeof terms.lock_in_months === "number") parts.push(`${terms.lock_in_months}-month lock-in`);
  if (typeof terms.refund_within_days === "number") parts.push(`refund within ${terms.refund_within_days} days`);
  if (terms.forfeit_on_any_breach === true) parts.push("deposit forfeited on any breach");
  if (terms.forfeit_on_any_breach === false) parts.push("no forfeiture");
  if (typeof terms.painting_inr === "number") parts.push(`${inr(terms.painting_inr)} at exit`);
  if (typeof terms.tenant_notice_months === "number") parts.push(`notice: tenant ${terms.tenant_notice_months} mo, landlord ${String(terms.landlord_notice_months)} mo`);
  if (typeof terms.notice_hours === "number") parts.push(terms.notice_hours === 0 ? "entry without notice" : `${terms.notice_hours} h notice before entry`);
  // A model's counter may use its own keys; show them as written rather than hide them.
  for (const [key, value] of Object.entries(terms)) if (!KNOWN_TERMS.includes(key)) parts.push(`${key.replaceAll("_", " ")}: ${String(value)}`);
  return parts.join(", ") || "—";
}

function DecisionCell({ decision, sections }: { decision: Decision; sections: Record<string, Section> }) {
  return (
    <div className="nego-cell">
      <div className="nego-badges">
        <span className={`badge ${DECISION[decision.decision]}`}>{decision.decision}</span>
        {decision.limit_override && (
          <span className="badge badge-blue">
            <Lock size={11} strokeWidth={2.2} aria-hidden />
            limit enforced
          </span>
        )}
        <VerdictBadge verdict={decision.verdict} />
        {decision.section_id && <SectionChip id={decision.section_id} sections={sections} />}
      </div>
      <p className="nego-text">{decision.reason}</p>
      {decision.counter_terms && <p className="nego-terms">Counter: {termsText(decision.counter_terms)}</p>}
    </div>
  );
}

/** Two rounds against the scripted landlord: offers on the left, the tenant agent's decisions on the right. */
export function Negotiation({ negotiation, findings, sections }: { negotiation: NegotiationData; findings: Finding[]; sections: Record<string, Section> }) {
  const status = STATUS[negotiation.status];
  const limits = negotiation.limits;
  const clauseText = (id: string) => findings.find((f) => f.clause_ref === id)?.clause_text;
  const opening = (id: string) => negotiation.rounds[0]?.offers.find((o) => o.clause_id === id)?.terms ?? {};
  const settled = negotiation.settled_clauses;

  return (
    <>
      <p className="nego-status">
        <span className={`badge ${status.className}`}>{status.label}</span>
        <span className="dim">
          Landlord: {PERSONA_LABEL[negotiation.persona]} · Your limits: lock-in up to {limits.max_lock_in_months} months, refund within{" "}
          {limits.refund_within_days} days, exit painting up to {inr(limits.max_exit_painting_inr)}
        </span>
      </p>

      {negotiation.rounds.map((round) => (
        <div key={round.round} className="panel nego-round">
          <div className="panel-head">
            <span>Round {round.round}</span>
            <span className="dim">{round.fallback ? "rule-based decision (model unavailable)" : `model ${(round.model_ms / 1000).toFixed(1)} s`}</span>
          </div>
          <div className="nego-cols nego-cols-head" aria-hidden>
            <span>
              <Store size={13} aria-hidden /> {PERSONA_LABEL[negotiation.persona]} offers
            </span>
            <span>
              <Bot size={13} aria-hidden /> Tenant agent decides
            </span>
          </div>
          {round.offers.map((offer) => {
            const decision = round.decisions.find((d) => d.clause_id === offer.clause_id);
            return (
              <div key={offer.clause_id} className="nego-cols">
                <div className="nego-cell">
                  <p className="nego-clause">
                    <span className="mono">{offer.clause_id}</span> {clauseTopic(offer.terms)}
                  </p>
                  <p className="nego-text">&ldquo;{offer.text}&rdquo;</p>
                  <p className="nego-terms">{termsText(offer.terms)}</p>
                </div>
                {decision ? (
                  <DecisionCell decision={decision} sections={sections} />
                ) : (
                  <div className="nego-cell">
                    <span className="badge">no decision</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}

      {negotiation.status === "running" && (
        <p className="dim" aria-live="polite">
          The landlord is answering. The next round appears here as soon as it is decided.
        </p>
      )}

      {negotiation.status !== "running" && (
        <figure className="fig-table">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Clause</th>
                  <th>Original</th>
                  <th>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(negotiation.agreed_terms).map(([id, terms]) => (
                  <tr key={id}>
                    <td className="mono">{id}</td>
                    <td className="dim">{clauseText(id) ?? termsText(opening(id))}</td>
                    <td>
                      {settled.includes(id) ? (
                        <>
                          <span className="badge badge-green">agreed</span> {termsText(terms)}
                        </>
                      ) : (
                        <>
                          <span className="badge badge-amber">open</span> Your standing ask: {typeof terms.ask === "string" ? terms.ask : termsText(terms)}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <figcaption>
            {negotiation.open_clauses.length
              ? `${settled.length} agreed, ${negotiation.open_clauses.length} still open after two rounds. The letter keeps your ask for open clauses.`
              : "Every clause agreed within your limits."}
          </figcaption>
        </figure>
      )}
    </>
  );
}
