import { inr } from "@/lib/format";
import type { Finding, Section, Severity } from "@/lib/types";
import { SectionChips } from "./SectionChip";

const SEVERITY: Record<Severity, string> = { high: "badge-red", medium: "badge-amber", low: "" };

const CATEGORY: Record<Finding["category"], string> = {
  deposit_forfeiture: "Deposit forfeiture",
  lock_in: "Lock-in",
  painting_or_cleaning_fixed: "Fixed painting or cleaning charge",
  notice_shortfall: "Notice shortfall",
  rent_escalation_excess: "Rent escalation",
};

/** Unfair clauses, worst first, each priced in rupees with the formula from CLAUDE.md. */
export function Findings({ findings, sections }: { findings: Finding[]; sections: Record<string, Section> }) {
  const total = findings.reduce((sum, f) => sum + f.money_at_risk_inr, 0);
  return (
    <ul className="rows">
      {findings.map((f) => (
        <li key={f.clause_ref} className="row">
          <div className="row-head">
            <h3>
              <span className="row-ref">{f.clause_ref}</span>
              {CATEGORY[f.category]}
            </h3>
            <span className="row-money">{inr(f.money_at_risk_inr)}</span>
          </div>
          <blockquote className="row-quote">{f.clause_text}</blockquote>
          <p className="row-text">{f.issue}</p>
          <p className="row-text">
            <strong>Ask:</strong> {f.ask}
          </p>
          <div className="row-foot">
            <span className={`badge ${SEVERITY[f.severity]}`}>{f.severity} severity</span>
            <SectionChips ids={f.section_ids} sections={sections} />
            {f.money_note && <span>{f.money_note}</span>}
          </div>
        </li>
      ))}
      <li className="row-total">
        <span>Total money at risk</span>
        <span className="row-money">{inr(total)}</span>
      </li>
    </ul>
  );
}
