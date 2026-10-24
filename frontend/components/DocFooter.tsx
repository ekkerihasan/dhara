import { USE_STUBS } from "@/lib/api";

const DEFAULT_NOTICE =
  "Dhara AI is not a lawyer and this is not legal advice. It explains the agreement against the cited sections so you can negotiate; for a dispute, consult an advocate.";

export function DocFooter({ notice = DEFAULT_NOTICE }: { notice?: string }) {
  return (
    <footer className="doc-foot">
      <p>
        <strong>Not a lawyer.</strong> {notice}
      </p>
      <p>
        Section text and links: India Code, PRS Legislative Research. Built at ChronoForge 2026, NITK Surathkal.
        {USE_STUBS && " Showing stubbed data (USE_STUBS)."}
      </p>
    </footer>
  );
}
