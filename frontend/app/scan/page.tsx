"use client";

import Link from "next/link";
import { useState } from "react";
import { Topbar } from "@/components/Topbar";
import { DocFooter } from "@/components/DocFooter";
import { Toc } from "@/components/Toc";
import sampleRun from "@/stubs/blr_flat.json";

const TOC = [{ id: "photo", title: "Prepare the photo" }, { id: "extracted", title: "Check the extracted text" }];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ScanPage() {
  const [file, setFile] = useState<File | null>(null);
  const [redacted, setRedacted] = useState(false);
  const [consent, setConsent] = useState(false);
  const [language, setLanguage] = useState("en-IN");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [sample, setSample] = useState(false);

  async function scan(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !redacted || !consent) return;
    setBusy(true); setError(""); setText(""); setCopied(false);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      const response = await fetch(`${API_URL}/api/ocr`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_base64: btoa(binary), image_already_redacted: redacted, consent_to_remote_ocr: consent, language }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not scan this photo.");
      setText(result.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the scan service.");
    } finally { setBusy(false); }
  }

  return <>
    <Topbar current="new" />
    <main className="doc"><Toc items={TOC} /><article className="doc-main">
      <p className="kicker">Dhara AI · Sarvam Vision</p>
      <h1 className="doc-title">Read an agreement photo</h1>
      <p className="doc-subtitle">Scan one page, check the extracted wording and amounts, then paste the corrected text into your agreement review.</p>
      <section className="section" id="photo">
        <h2>Prepare the photo</h2>
        <p>Before uploading, cover Aadhaar, PAN and phone numbers in an image editor and save a flattened copy. Selecting a checkbox does not inspect or redact your image.</p>
        <p>This sends the photo to Sarvam Vision for remote OCR. Dhara keeps it in memory for this request and strips image metadata; Sarvam may retain its processing job. Provider retention and deletion are not controlled by Dhara. Do not upload a photo you are unwilling to share with Sarvam.</p>
        <form onSubmit={scan} style={{ display: "grid", gap: 16, maxWidth: 640 }}>
          <div className="field">
            <label className="field-label" htmlFor="photo-file">Agreement photo</label>
            <input id="photo-file" type="file" accept="image/jpeg,image/png" disabled={busy} onChange={(event) => {
              const chosen = event.target.files?.[0] ?? null;
              setText(""); setError(""); setSample(false); setRedacted(false); setConsent(false);
              if (chosen && (!['image/jpeg', 'image/png'].includes(chosen.type) || chosen.size > 8 * 1024 * 1024)) {
                setFile(null); setError("Choose a JPEG or PNG photo up to 8 MB.");
              } else setFile(chosen);
            }} />
            <span className="field-hint">JPEG or PNG, up to 8 MB.</span>
          </div>
          <div className="field" style={{ maxWidth: 240 }}>
            <label className="field-label" htmlFor="photo-language">Document language</label>
            <select id="photo-language" value={language} disabled={busy} onChange={(event) => setLanguage(event.target.value)}>
              <option value="en-IN">English</option><option value="kn-IN">Kannada</option><option value="hi-IN">Hindi</option>
            </select>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <input type="checkbox" checked={redacted} disabled={busy} onChange={(event) => setRedacted(event.target.checked)} style={{ marginTop: 4 }} />
            <span>I have already removed Aadhaar, PAN and phone numbers from this photo.</span>
          </label>
          <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <input type="checkbox" checked={consent} disabled={busy} onChange={(event) => setConsent(event.target.checked)} style={{ marginTop: 4 }} />
            <span>I agree to send this photo to Sarvam for OCR.</span>
          </label>
          <div className="form-actions" style={{ marginTop: 0 }}>
            <button className="btn primary" disabled={busy || !file || !redacted || !consent}>{busy ? "Reading the photo…" : "Scan with Sarvam Vision"}</button>
          </div>
        </form>
        {busy && <p role="status">This can take a minute. Keep this page open.</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {error && !text && <div className="form-actions">
          <button className="btn" type="button" onClick={() => { setText(sampleRun.agreement_text); setSample(true); setError(""); }}>Use the sample agreement text instead</button>
        </div>}
      </section>
      {text && <section className="section" id="extracted">
        <h2>Check the extracted text</h2>
        {sample && <div className="callout callout-warning"><div><p><strong>Sample text.</strong> The scan service is unavailable, so this is the sample Bengaluru flat agreement, not text read from your photo.</p></div></div>}
        <p>OCR can misread clauses and amounts. Correct the text below before reviewing it. Detected identifiers in the OCR text have been redacted again.</p>
        <label htmlFor="ocr-text">Agreement text</label>
        <textarea id="ocr-text" rows={18} value={text} onChange={(event) => { setText(event.target.value); setCopied(false); }} style={{ width: "100%" }} />
        <button className="btn" onClick={async () => {
          try { await navigator.clipboard.writeText(text); setCopied(true); setError(""); }
          catch { setError("Select and copy the text above manually."); }
        }}>{copied ? "Copied" : "Copy corrected text"}</button>
        <p><Link href="/">Open the agreement review</Link> and paste the corrected text. For more pages, repeat the scan and combine the checked text.</p>
      </section>}
      <DocFooter />
    </article></main>
  </>;
}
