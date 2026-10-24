"use client";

import { useState } from "react";
import { inr } from "@/lib/format";

export interface ClauseTypeRow {
  category: string;
  count: number;
  clauses: { task: string; clause_ref: string; amount_inr: number }[];
}

const LABEL: Record<string, string> = {
  painting_or_cleaning_fixed: "Fixed painting or cleaning charge",
  deposit_forfeiture: "Deposit forfeiture",
  lock_in: "Lock-in payment",
  notice_shortfall: "Notice shortfall",
  rent_escalation_excess: "Rent increase above 10%",
  wear_and_tear: "Wear-and-tear deduction",
};

/**
 * Horizontal bars, one series: how often each unfair clause type appears across the test agreements.
 * Each bar carries its count as a direct label; hover or focus lists the clauses behind it; a table view follows.
 */
export function ClauseTypesChart({ rows }: { rows: ClauseTypeRow[] }) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(...rows.map((r) => r.count), 1);

  return (
    <figure className="figure">
      <div className="bars" role="img" aria-label="Unfair or disputed clause types across the three test agreements">
        {rows.map((r) => (
          <div key={r.category} className="bar-row">
            <span className="bar-label">{LABEL[r.category] ?? r.category}</span>
            <div
              className="bar-track"
              tabIndex={0}
              onMouseEnter={() => setActive(r.category)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(r.category)}
              onBlur={() => setActive(null)}
              aria-label={`${LABEL[r.category] ?? r.category}: ${r.count}`}
            >
              <span className="bar" style={{ width: `${(r.count / max) * 100}%` }} />
              <span className="bar-value">{r.count}</span>
              {active === r.category && (
                <span className="bar-tip" role="tooltip">
                  {r.clauses.map((c) => (
                    <span key={`${c.task}-${c.clause_ref}`}>
                      {c.task} · {c.clause_ref} · {inr(c.amount_inr)}
                    </span>
                  ))}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <figcaption>
        Unfair or disputed clauses by type across the three synthetic test agreements (move-out counts disputed deductions only). Hover a bar for
        the clauses behind it.
      </figcaption>
      <details className="io" style={{ marginTop: 8 }}>
        <summary>Show as a table</summary>
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table>
            <thead>
              <tr>
                <th>Clause type</th>
                <th className="num">Count</th>
                <th>Clauses</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.category}>
                  <td>{LABEL[r.category] ?? r.category}</td>
                  <td className="num">{r.count}</td>
                  <td className="dim">{r.clauses.map((c) => `${c.task} ${c.clause_ref} (${inr(c.amount_inr)})`).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
