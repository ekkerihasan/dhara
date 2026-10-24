"use client";

import { Info, Scale, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { answerQuestion, approveDraft, getRun } from "@/lib/api";
import { inr, date, LOCAL_BODY_LABEL, STATUS_LABEL } from "@/lib/format";
import type { ApprovalStep, QuestionStep, Run, VerifierStep } from "@/lib/types";
import { AgentGlance } from "./AgentGlance";
import { CitationCheck } from "./CitationCheck";
import { DocFooter } from "./DocFooter";
import { DraftPanel } from "./DraftPanel";
import { Findings } from "./Findings";
import { appliesLabel, Jurisdiction } from "./Jurisdiction";
import { QuestionCard } from "./QuestionCard";
import { SectionChips } from "./SectionChip";
import { Toc, type TocItem } from "./Toc";
import { Trace } from "./Trace";

const POLL_MS = 1500;

const FULL_TOC: TocItem[] = [
  { id: "law", title: "Governing law" },
  { id: "findings", title: "Unfair clauses" },
  { id: "draft", title: "Counter-proposal" },
  { id: "citations", title: "Citation check" },
  { id: "trace", title: "Decision trace" },
];
const PAUSED_TOC: TocItem[] = [{ id: "trace", title: "Decision trace" }];

export function ReviewDocument({ id }: { id: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRun(await getRun(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the run.");
    }
  }, [id]);

  useEffect(() => {
    let alive = true;
    getRun(id)
      .then((r) => alive && setRun(r))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : "Could not load the run."));
    return () => {
      alive = false;
    };
  }, [id]);

  // Live mode: keep polling while the agent is working.
  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [run?.status, load]);

  if (error) {
    return (
      <main className="doc">
        <div />
        <div className="doc-main">
          <div className="callout callout-danger">
            <TriangleAlert size={16} aria-hidden />
            <p>{error}</p>
          </div>
          <Link className="btn" href="/">
            Start a new review
          </Link>
        </div>
      </main>
    );
  }

  if (!run) {
    return (
      <main className="doc">
        <div />
        <div className="doc-main" aria-busy="true">
          <div className="skeleton" style={{ width: "30%" }} />
          <div className="skeleton" style={{ width: "80%", height: 36 }} />
          <div className="skeleton" style={{ width: "60%" }} />
        </div>
      </main>
    );
  }

  const paused = run.status === "needs_input" || run.status === "running";
  const question = run.trace.find((s): s is QuestionStep => s.type === "question" && s.answer === null) ?? null;
  const verifier = run.trace.filter((s): s is VerifierStep => s.type === "verifier");
  const approval = run.trace.find((s): s is ApprovalStep => s.type === "approval") ?? null;
  const toolCalls = run.trace.filter((s) => s.type === "tool_call").length;
  const total = run.findings.reduce((sum, f) => sum + f.money_at_risk_inr, 0);
  const blocked = verifier.filter((s) => s.verdict === "blocked").length;
  const cited = verifier.filter((s) => s.verdict === "cited").length;

  const onAnswer = async (value: string) => {
    if (!question) return;
    await answerQuestion(run.id, question.field, value);
    await load();
  };
  const onApprove = async () => {
    await approveDraft(run.id, run.drafts[0].id);
    await load();
  };

  return (
    <main className="doc">
      <Toc items={paused ? PAUSED_TOC : FULL_TOC} />
      <article className="doc-main">
        <p className="kicker">
          Review report · <span className="mono">{run.id}</span>
          <span className={`badge ${run.status === "approved" ? "badge-green" : paused ? "badge-amber" : "badge-blue"}`}>{STATUS_LABEL[run.status]}</span>
        </p>
        <h1 className="doc-title">{run.title}</h1>
        <p className="doc-subtitle">
          What governs this rental, which clauses cost the tenant money, and the message the agent drafted to fix them, with every step it took.
        </p>

        <dl className="meta">
          <div>
            <dt>Rent</dt>
            <dd>{run.facts.rent_per_month ? `${inr(run.facts.rent_per_month)}/month` : "—"}</dd>
          </div>
          <div>
            <dt>Deposit</dt>
            <dd>{run.facts.deposit_inr ? inr(run.facts.deposit_inr) : "—"}</dd>
          </div>
          <div>
            <dt>Built</dt>
            <dd>{run.facts.built_year ?? (question ? "Asked" : "—")}</dd>
          </div>
          <div>
            <dt>Local body</dt>
            <dd>{run.facts.local_body ? LOCAL_BODY_LABEL[run.facts.local_body] : "—"}</dd>
          </div>
          <div>
            <dt>Tool calls</dt>
            <dd>
              {toolCalls} of {run.max_tool_calls}
            </dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{date(run.created_at)}</dd>
          </div>
        </dl>

        {question && <QuestionCard step={question} onAnswer={onAnswer} />}

        {!paused && run.governing_law && (
          <>
            <AgentGlance trace={run.trace} />
            <div className="stats">
              <div className="stat is-danger">
                <div className="stat-value">{inr(total)}</div>
                <div className="stat-label">Money at risk across {run.findings.length} clauses</div>
              </div>
              <div className="stat">
                <div className="stat-value is-text">{appliesLabel(run.governing_law.rent_act_applies)}</div>
                <div className="stat-label">Karnataka Rent Act, 1999</div>
              </div>
              <div className="stat is-safe">
                <div className="stat-value">{cited}</div>
                <div className="stat-label">Claims cited to a section</div>
              </div>
              <div className="stat is-danger">
                <div className="stat-value">{blocked}</div>
                <div className="stat-label">Claims blocked by the verifier</div>
              </div>
            </div>

            <section className="section" id="law">
              <h2>Governing law</h2>
              <div className={`callout ${run.governing_law.rent_act_applies === true ? "callout-safe" : "callout-warning"}`}>
                <Scale size={16} aria-hidden />
                <div>
                  <p>{run.governing_law.summary}</p>
                  <p style={{ marginTop: 10 }}>
                    <SectionChips ids={run.governing_law.section_ids} sections={run.sections} />
                  </p>
                </div>
              </div>
              <Jurisdiction law={run.governing_law} sections={run.sections} />
              <p>
                Read with: <SectionChips ids={run.governing_law.governs} sections={run.sections} />
              </p>
            </section>

            <section className="section" id="findings">
              <h2>Unfair clauses</h2>
              <p>Each clause is priced with a fixed formula, not by the model, so the same agreement always gives the same number.</p>
              <Findings findings={run.findings} sections={run.sections} />
            </section>

            {run.drafts[0] && (
              <section className="section" id="draft">
                <h2>Counter-proposal</h2>
                <p>
                  Written only from cited claims.
                  {blocked > 0 && ` The ${blocked} blocked ${blocked === 1 ? "claim was" : "claims were"} removed before drafting.`}
                </p>
                <DraftPanel draft={run.drafts[0]} initialLanguage={run.facts.language} approval={approval} onApprove={onApprove} />
              </section>
            )}

            <section className="section" id="citations">
              <h2>Citation check</h2>
              <p>
                Every legal claim must carry a section id from <code>law/karnataka.json</code> that applies in Karnataka. A section from a law
                Karnataka has not adopted, or a legal claim with no section, is blocked.
              </p>
              <figure className="fig-table">
                <CitationCheck steps={verifier} sections={run.sections} />
                <figcaption>Verifier verdicts for this run. Red rows never reach the tenant or the landlord.</figcaption>
              </figure>
            </section>
          </>
        )}

        <section className="section" id="trace">
          <h2>Decision trace</h2>
          <p>Every step the agent took, in order: its plan, the question it asked, each tool call with inputs and outputs, and each verifier verdict.</p>
          {paused && (
            <div className="callout">
              <Info size={16} aria-hidden />
              <p>The agent paused after reading the agreement. It will not guess a fact that decides which law applies.</p>
            </div>
          )}
          <Trace trace={run.trace} sections={run.sections} />
        </section>

        <DocFooter notice={run.notice} />
      </article>
    </main>
  );
}
