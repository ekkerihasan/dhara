import type { GoverningLaw, JurisdictionStatus, Section } from "@/lib/types";
import { SectionChip } from "./SectionChip";

const STATUS: Record<JurisdictionStatus, { className: string; label: string }> = {
  excluded: { className: "badge-red", label: "Excludes the Act" },
  needs_input: { className: "badge-amber", label: "Needs input" },
  conditional: { className: "badge-blue", label: "Conditional" },
};

// Field names returned in check_jurisdiction's `missing` list.
const MISSING_LABEL: Record<string, string> = {
  standard_rent_monthly: "Statutory (standard) rent",
  ownership_type: "Ownership type",
  other_exemptions_checked: "Other exemptions checked",
  tenancy_date: "Tenancy start date",
  completion_date: "Exact completion date",
};

/** applies is true, false or null; null means unresolved and must never read as "does not apply". */
export function appliesLabel(applies: boolean | null): string {
  if (applies === null) return "Unresolved";
  return applies ? "Applies (conditional)" : "Does not apply";
}

/** The Rent Act test, reason by reason, as check_jurisdiction returned it. */
export function Jurisdiction({ law, sections }: { law: GoverningLaw; sections: Record<string, Section> }) {
  return (
    <>
      <figure className="fig-table">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Section</th>
                <th>Result</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {law.reasons.map((r) => (
                <tr key={r.section_id}>
                  <td>
                    <SectionChip id={r.section_id} sections={sections} />
                  </td>
                  <td>
                    <span className={`badge ${STATUS[r.status].className}`}>{STATUS[r.status].label}</span>
                  </td>
                  <td>{r.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <figcaption>Karnataka Rent Act applicability test (check_jurisdiction). {law.note}</figcaption>
      </figure>
      {law.missing.length > 0 && (
        <p>
          Still to confirm:{" "}
          <span className="chips">
            {law.missing.map((m) => (
              <span key={m} className="badge badge-amber">
                {MISSING_LABEL[m] ?? m}
              </span>
            ))}
          </span>
        </p>
      )}
    </>
  );
}
