"use client";

import { FileUp, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { createRun } from "@/lib/api";
import { LOCAL_BODY_LABEL } from "@/lib/format";
import { SAMPLE_AGREEMENT } from "@/stubs/sample-agreement";
import type { Facts, Language, LocalBody, PremisesUse } from "@/lib/types";

const MAX_PDF_BYTES = 8 * 1024 * 1024; // same 8 MB limit as the prototype reader

function toNumber(value: string): number | null {
  const n = Number(value);
  return value.trim() && Number.isFinite(n) ? n : null;
}

/** Agreement (PDF or pasted text) plus the facts the Rent Act test needs. Blank built year is allowed: the agent asks. */
export function IntakeForm() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [over, setOver] = useState(false);
  const [rent, setRent] = useState("25000");
  const [deposit, setDeposit] = useState("250000");
  const [builtYear, setBuiltYear] = useState("");
  const [renovationYear, setRenovationYear] = useState("");
  const [localBody, setLocalBody] = useState<LocalBody>("municipal_corporation");
  const [use, setUse] = useState<PremisesUse>("residential");
  const [language, setLanguage] = useState<Language>("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (f: File | undefined) => {
    if (!f) return;
    if (f.type !== "application/pdf") return setError("Only PDF files are supported. Paste the text instead.");
    if (f.size > MAX_PDF_BYTES) return setError("The PDF is over 8 MB.");
    setError(null);
    setFile(f);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file && !text.trim()) return setError("Upload the agreement PDF or paste its text.");
    if (!toNumber(rent)) return setError("Enter the monthly rent.");
    const facts: Facts = {
      rent_per_month: toNumber(rent),
      deposit_inr: toNumber(deposit),
      built_year: toNumber(builtYear),
      substantial_renovation_year: toNumber(renovationYear),
      local_body: localBody,
      premises_use: use,
      language,
    };
    setBusy(true);
    setError(null);
    try {
      const id = await createRun({ file, text: text.trim() || null, facts });
      router.push(`/review/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the review.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate>
      <section className="section" id="agreement">
        <h2>The agreement</h2>
        <p>Personal numbers (Aadhaar, PAN, phone) are redacted before the model sees anything. The file is not stored.</p>
        <label
          className={`dropzone ${over ? "is-over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            pick(e.dataTransfer.files[0]);
          }}
        >
          <FileUp size={22} strokeWidth={1.6} aria-hidden />
          {file ? (
            <span>
              <strong>{file.name}</strong> · {(file.size / 1024).toFixed(0)} KB
            </span>
          ) : (
            <span>
              <strong>Drop the agreement PDF</strong> or click to choose
            </span>
          )}
          <span className="field-hint">PDF, up to 8 MB</span>
          <input ref={fileInput} type="file" accept="application/pdf" onChange={(e) => pick(e.target.files?.[0])} />
        </label>
        {file && (
          <button
            type="button"
            className="btn btn-sm"
            style={{ marginTop: 8 }}
            onClick={() => {
              setFile(null);
              if (fileInput.current) fileInput.current.value = "";
            }}
          >
            <X size={14} aria-hidden /> Remove file
          </button>
        )}
        <div className="or-rule">or paste the text</div>
        <div className="form-actions" style={{ marginTop: 0, marginBottom: 8 }}>
          <button type="button" className="btn btn-sm" onClick={() => setText(SAMPLE_AGREEMENT)}>
            Use the sample agreement
          </button>
          <span className="field-hint">A synthetic 11-month Bengaluru flat agreement with 12 clauses.</span>
        </div>
        <div className="field" style={{ maxWidth: 640 }}>
          <label className="sr-only" htmlFor="text">
            Agreement text
          </label>
          <textarea id="text" placeholder="1. The Owner agrees to let out…" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      </section>

      <section className="section" id="facts">
        <h2>Facts about the rental</h2>
        <p>These decide whether the Karnataka Rent Act applies. Leave the built year blank if you do not know it: the agent will ask.</p>
        <div className="form-grid">
          <div className="field">
            <label className="field-label" htmlFor="rent">
              Monthly rent
            </label>
            <div className="input-prefix">
              <span>₹</span>
              <input id="rent" type="number" inputMode="numeric" min={0} value={rent} onChange={(e) => setRent(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="deposit">
              Security deposit <span className="optional">(optional)</span>
            </label>
            <div className="input-prefix">
              <span>₹</span>
              <input id="deposit" type="number" inputMode="numeric" min={0} value={deposit} onChange={(e) => setDeposit(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="built">
              Year built <span className="optional">(optional)</span>
            </label>
            <input id="built" type="number" inputMode="numeric" placeholder="Not sure" value={builtYear} onChange={(e) => setBuiltYear(e.target.value)} />
            <span className="field-hint">Rent Act s.2(3)(f): exempt for 15 years.</span>
          </div>
          <div className="field">
            <label className="field-label" htmlFor="renovated">
              Substantially renovated <span className="optional">(optional)</span>
            </label>
            <input id="renovated" type="number" inputMode="numeric" placeholder="Year" value={renovationYear} onChange={(e) => setRenovationYear(e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="local-body">
              Local body
            </label>
            <select id="local-body" value={localBody} onChange={(e) => setLocalBody(e.target.value as LocalBody)}>
              {(Object.keys(LOCAL_BODY_LABEL) as LocalBody[]).map((k) => (
                <option key={k} value={k}>
                  {LOCAL_BODY_LABEL[k]}
                </option>
              ))}
            </select>
            <span className="field-hint">Bengaluru, Mysuru, Mangaluru are Part A.</span>
          </div>
          <div className="field">
            <span className="field-label">Use</span>
            <div className="segmented" role="radiogroup" aria-label="Use">
              {(["residential", "non_residential"] as PremisesUse[]).map((u) => (
                <label key={u}>
                  <input type="radio" name="use" value={u} checked={use === u} onChange={() => setUse(u)} />
                  {u === "residential" ? "Residential" : "Non-residential"}
                </label>
              ))}
            </div>
          </div>
          <div className="field span-2">
            <span className="field-label">Draft messages in</span>
            <div className="segmented" role="radiogroup" aria-label="Language">
              <label>
                <input type="radio" name="lang" value="en" checked={language === "en"} onChange={() => setLanguage("en")} />
                English
              </label>
              <label lang="kn">
                <input type="radio" name="lang" value="kn" checked={language === "kn"} onChange={() => setLanguage("kn")} />
                ಕನ್ನಡ
              </label>
            </div>
          </div>
        </div>
        <div className="form-actions">
          <button className="btn btn-lg primary" type="submit" disabled={busy}>
            {busy ? "Starting the agent…" : "Review the agreement"}
          </button>
          <span className="field-hint">You approve every message before it is sent.</span>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </section>
    </form>
  );
}
