import type { Section } from "@/lib/types";

/** A section id linked to its source. Sections that do not apply in Karnataka are struck through in red. */
export function SectionChip({ id, sections }: { id: string; sections: Record<string, Section> }) {
  const section = sections[id];
  if (!section) return <span className="chip">{id}</span>;
  const wrongLaw = !section.applies_in_karnataka;
  return (
    <a
      className={`chip ${wrongLaw ? "is-wrong-law" : ""}`}
      href={section.source_url}
      target="_blank"
      rel="noreferrer"
      title={`${section.act}, s.${section.section}: ${section.title}${wrongLaw ? " (does not apply in Karnataka)" : ""}`}
    >
      {id}
    </a>
  );
}

export function SectionChips({ ids, sections }: { ids: string[]; sections: Record<string, Section> }) {
  if (!ids.length) return <span className="dim">no section</span>;
  return (
    <span className="chips">
      {ids.map((id) => (
        <SectionChip key={id} id={id} sections={sections} />
      ))}
    </span>
  );
}
