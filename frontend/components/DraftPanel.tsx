"use client";

import { CalendarClock, Copy, Send } from "lucide-react";
import { useState } from "react";
import type { ApprovalStep, Draft, Language } from "@/lib/types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ" },
];

/** The outgoing message. send_and_schedule refuses anything not approved, and it records a follow-up; it does not deliver. */
export function DraftPanel({
  draft,
  initialLanguage,
  approval,
  onApprove,
}: {
  draft: Draft;
  initialLanguage: Language;
  approval: ApprovalStep | null;
  onApprove: () => Promise<void>;
}) {
  const available = LANGUAGES.filter((l) => draft.text[l.code]);
  const [language, setLanguage] = useState<Language>(draft.text[initialLanguage] ? initialLanguage : (available[0]?.code ?? "en"));
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const approve = async () => {
    setBusy(true);
    try {
      await onApprove();
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft.text[language] ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked: the text is selectable
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span>
          To: {draft.to} · Tone: {draft.tone}
        </span>
        <div className="segmented" role="group" aria-label="Draft language">
          {available.map((l) => (
            <button key={l.code} type="button" aria-pressed={language === l.code} onClick={() => setLanguage(l.code)} lang={l.code}>
              {l.label}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body" lang={language}>
        {draft.text[language]}
      </div>
      {draft.note && <div className="panel-note">{draft.note}</div>}
      <div className="panel-foot">
        {approval ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--safe)" }}>
            <CalendarClock size={15} aria-hidden />
            Approved. Follow-up on {approval.follow_up_date}. Copy the text and send it yourself.
          </span>
        ) : (
          <span>Review the text, then approve it. Dhara never sends anything on its own.</span>
        )}
        <span className="spacer" />
        <button className="btn btn-sm" type="button" onClick={copy}>
          <Copy size={14} aria-hidden />
          {copied ? "Copied" : "Copy"}
        </button>
        {!approval && (
          <button className="btn btn-sm primary" type="button" onClick={approve} disabled={busy}>
            <Send size={14} aria-hidden />
            {busy ? "Approving…" : "Approve"}
          </button>
        )}
      </div>
    </div>
  );
}
