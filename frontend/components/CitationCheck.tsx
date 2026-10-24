import type { Section, VerifierStep } from "@/lib/types";
import { SectionChip } from "./SectionChip";
import { VerdictBadge } from "./VerdictBadge";

/** Every claim the agent wanted to make, and what the verifier did with it. Blocked rows never reach a draft. */
export function CitationCheck({ steps, sections }: { steps: VerifierStep[]; sections: Record<string, Section> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Section</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s) => (
            <tr key={s.index} className={s.verdict === "blocked" ? "is-blocked" : undefined}>
              <td>
                {s.claim}
                <div className="dim" style={{ fontSize: 13, marginTop: 4 }}>
                  {s.reason}
                </div>
              </td>
              <td>{s.section_id ? <SectionChip id={s.section_id} sections={sections} /> : <span className="dim">none</span>}</td>
              <td>
                <VerdictBadge verdict={s.verdict} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
