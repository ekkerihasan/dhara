"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createMoveout } from "@/lib/api";
import { date, inr } from "@/lib/format";
import type { Language, MoveoutInput } from "@/lib/types";
import moveout from "@/stubs/moveout.json";

const SAMPLE = moveout.sample_request as Omit<MoveoutInput, "deposit_inr" | "language">;
const SAMPLE_DEPOSIT = moveout.deposit_inr;

/** Move-out intake: the agreement, the dated move-in checklist and the deductions the landlord claims. */
export function MoveoutIntake() {
  const router = useRouter();
  const [input, setInput] = useState<Omit<MoveoutInput, "language"> | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setAmount = (index: number, value: string) => {
    if (!input) return;
    const deductions = input.deductions.map((d, i) => (i === index ? { ...d, amount_inr: Math.max(0, Math.round(Number(value) || 0)) } : d));
    setInput({ ...input, deductions });
  };

  const submit = async () => {
    if (!input) return;
    setBusy(true);
    setError(null);
    try {
      const id = await createMoveout({ ...input, language });
      router.push(`/moveout/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the move-out review.");
      setBusy(false);
    }
  };

  return (
    <>
      <section className="section" id="evidence">
        <h2>Agreement, move-in evidence and claimed deductions</h2>
        <p>Dhara checks each deduction against the agreement and the dated checklist made at move-in.</p>
        {!input ? (
          <div className="form-actions" style={{ marginTop: 0 }}>
            <button type="button" className="btn primary" onClick={() => setInput({ ...SAMPLE, deposit_inr: SAMPLE_DEPOSIT })}>
              Use the sample move-out
            </button>
            <span className="field-hint">The synthetic move-out from the moveout evaluation task.</span>
          </div>
        ) : (
          <>
            <figure className="fig-table">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Entry</th>
                      <th>Date</th>
                      <th>Item</th>
                      <th>Condition at move-in</th>
                    </tr>
                  </thead>
                  <tbody>
                    {input.checklist.map((c) => (
                      <tr key={c.id}>
                        <td className="mono">{c.id}</td>
                        <td style={{ whiteSpace: "nowrap" }}>{date(c.date)}</td>
                        <td>{c.item}</td>
                        <td>{c.condition}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <figcaption>Move-in checklist.</figcaption>
            </figure>
            <figure className="fig-table">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Deduction</th>
                      <th>Clause</th>
                      <th className="num">Claimed (₹)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {input.deductions.map((d, i) => (
                      <tr key={`${d.clause_ref}-${d.label}`}>
                        <td style={{ textTransform: "capitalize" }}>{d.label}</td>
                        <td className="mono">{d.clause_ref}</td>
                        <td className="num">
                          <label className="sr-only" htmlFor={`amount-${i}`}>
                            Claimed amount for {d.label}
                          </label>
                          <input id={`amount-${i}`} type="number" inputMode="numeric" min={0} value={d.amount_inr} onChange={(e) => setAmount(i, e.target.value)} style={{ maxWidth: 120, textAlign: "right" }} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <figcaption>
                Deductions the landlord claims from a deposit of {inr(input.deposit_inr)}. Amounts can be edited.
              </figcaption>
            </figure>
            <div className="field" style={{ marginBottom: 16 }}>
              <span className="field-label">Draft the challenge in</span>
              <div className="segmented" role="radiogroup" aria-label="Language">
                <label>
                  <input type="radio" name="moveout-lang" checked={language === "en"} onChange={() => setLanguage("en")} />
                  English
                </label>
                <label lang="kn">
                  <input type="radio" name="moveout-lang" checked={language === "kn"} onChange={() => setLanguage("kn")} />
                  ಕನ್ನಡ
                </label>
                <label lang="hi">
                  <input type="radio" name="moveout-lang" checked={language === "hi"} onChange={() => setLanguage("hi")} />
                  हिन्दी
                </label>
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn-lg primary" onClick={submit} disabled={busy}>
                {busy ? "Starting the agent…" : "Check the deductions"}
              </button>
              <span className="field-hint">Nothing goes out without your approval.</span>
            </div>
          </>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </section>
    </>
  );
}
