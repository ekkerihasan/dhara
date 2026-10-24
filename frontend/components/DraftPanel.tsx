"use client";

import { CalendarClock, Copy, MessageCircle, Send } from "lucide-react";
import { useState } from "react";
import type { ApprovalStep, Draft, Language } from "@/lib/types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "en", label: "English" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "hi", label: "हिन्दी" },
];

/** The outgoing message. send_and_schedule refuses anything not approved, and it records a follow-up; it does not deliver. */
export function DraftPanel({
  draft,
  initialLanguage,
  approval,
  onApprove,
  approveLabel = "Approve",
  waiting = null,
}: {
  draft: Draft;
  initialLanguage: Language;
  approval: ApprovalStep | null;
  onApprove: (() => Promise<void>) | null; // null: a letter to copy and send yourself; nothing to approve here
  approveLabel?: string;
  waiting?: string | null; // why approval is not possible yet, e.g. the negotiation is still running
}) {
  const available = LANGUAGES.filter((l) => draft.text[l.code]);
  const [language, setLanguage] = useState<Language>(draft.text[initialLanguage] ? initialLanguage : (available[0]?.code ?? "en"));
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const approve = async () => {
    if (!onApprove) return;
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

  // WhatsApp opens with the letter filled in; the tenant picks the contact and presses send there.
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(draft.text[language] ?? "")}`;

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
            Approved. Follow-up on {approval.follow_up_date}. Copy it or share it on WhatsApp; you send it yourself.
          </span>
        ) : (
          <span>{waiting ?? (onApprove ? "Review the text, then approve it. Dhara never sends anything on its own." : "Copy it and send it yourself.")}</span>
        )}
        <span className="spacer" />
        <button className="btn btn-sm" type="button" onClick={copy}>
          <Copy size={14} aria-hidden />
          {copied ? "Copied" : "Copy"}
        </button>
        {approval && (
          <a className="btn btn-sm" href={whatsapp} target="_blank" rel="noopener noreferrer">
            <MessageCircle size={14} aria-hidden />
            Share on WhatsApp
          </a>
        )}
        {!approval && onApprove && (
          <button className="btn btn-sm primary" type="button" onClick={approve} disabled={busy || Boolean(waiting)}>
            <Send size={14} aria-hidden />
            {busy ? "Approving…" : approveLabel}
          </button>
        )}
      </div>
    </div>
  );
}
