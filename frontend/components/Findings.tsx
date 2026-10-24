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

/** Unfair clauses, worst first, each priced in rupees by compute_money. Amounts can overlap, so they are never added up. */
export function Findings({ findings, sections }: { findings: Finding[]; sections: Record<string, Section> }) {
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
        <span className="dim" style={{ fontWeight: 400, fontSize: 13.5 }}>
          Each amount is that clause&apos;s own exposure. They can overlap (a forfeited deposit can&apos;t also pay for painting), so they are not
          added up.
        </span>
      </li>
    </ul>
  );
}
