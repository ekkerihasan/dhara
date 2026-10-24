"use client";

import { CircleHelp } from "lucide-react";
import { useState } from "react";
import type { QuestionStep } from "@/lib/types";

/** Shown when a run is paused with status needs_input: the agent will not guess a jurisdiction input. */
export function QuestionCard({ step, onAnswer }: { step: QuestionStep; onAnswer: (value: string) => Promise<void> }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const numeric = step.field === "built_year" || step.field === "substantial_renovation_year";

  /** An empty value means "I don't know": the agent continues with the law marked unresolved. */
  const send = async (answer: string) => {
    setBusy(true);
    setError(null);
    try {
      await onAnswer(answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the answer.");
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const year = Number(value);
    if (numeric && (!Number.isInteger(year) || year < 1900 || year > new Date().getFullYear())) {
      setError("Enter a year between 1900 and this year.");
      return;
    }
    await send(value.trim());
  };

  return (
    <section className="question-card" aria-live="polite">
      <p className="q-kicker">
        <CircleHelp size={14} strokeWidth={2} aria-hidden />
        The agent needs one answer
      </p>
      <h2>{step.question}</h2>
      <p>{step.why}</p>
      <form onSubmit={submit}>
        <label className="sr-only" htmlFor="answer">
          {step.question}
        </label>
        <input
          id="answer"
          type={numeric ? "number" : "text"}
          inputMode={numeric ? "numeric" : undefined}
          placeholder={numeric ? "e.g. 2019" : ""}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          required
          autoFocus
        />
        <button className="btn primary" type="submit" disabled={busy || !value}>
          {busy ? "Resuming…" : "Answer and continue"}
        </button>
        <button className="btn" type="button" disabled={busy} onClick={() => send("")}>
          I don&apos;t know
        </button>
      </form>
      {error && <p className="form-error">{error}</p>}
    </section>
  );
}
