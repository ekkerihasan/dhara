import { Bot, ChevronRight, CircleHelp, FileText, Handshake, ListTodo, Receipt, Send, ShieldCheck, Store, Wrench } from "lucide-react";
import { inr, time } from "@/lib/format";
import type { Section, TraceStep } from "@/lib/types";
import { PERSONA_LABEL, termsText } from "./Negotiation";
import { SectionChip } from "./SectionChip";
import { VerdictBadge } from "./VerdictBadge";

const ICON = { size: 15, strokeWidth: 1.9, "aria-hidden": true } as const;

const KIND: Record<TraceStep["type"], string> = {
  plan: "Plan",
  question: "Question",
  tool_call: "Tool call",
  verifier: "Verifier",
  draft: "Draft",
  approval: "Approval",
  landlord_offer: "Landlord offer",
  tenant_decision: "Tenant decision",
  negotiation_settled: "Negotiation",
  needs_itemisation: "Itemisation first",
};

function badgeClass(step: TraceStep): string {
  return step.type === "verifier" ? `v-${step.verdict}` : `t-${step.type}`;
}

function StepIcon({ step }: { step: TraceStep }) {
  switch (step.type) {
    case "plan":
      return <ListTodo {...ICON} />;
    case "question":
      return <CircleHelp {...ICON} />;
    case "tool_call":
      return <Wrench {...ICON} />;
    case "verifier":
      return <ShieldCheck {...ICON} />;
    case "draft":
      return <FileText {...ICON} />;
    case "approval":
      return <Send {...ICON} />;
    case "landlord_offer":
      return <Store {...ICON} />;
    case "tenant_decision":
      return <Bot {...ICON} />;
    case "negotiation_settled":
      return <Handshake {...ICON} />;
    case "needs_itemisation":
      return <Receipt {...ICON} />;
  }
}

function Json({ value }: { value: unknown }) {
  return <pre className="codeblock">{JSON.stringify(value, null, 2)}</pre>;
}

function StepBody({ step, sections }: { step: TraceStep; sections: Record<string, Section> }) {
  switch (step.type) {
    case "plan":
      return (
        <>
          <div className="timeline-head">
            <h3>Planned the review</h3>
          </div>
          <ol>
            {step.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </>
      );
    case "question":
      return (
        <>
          <div className="timeline-head">
            <h3>Asked the tenant</h3>
            {step.answer === null ? <span className="badge badge-amber">Waiting</span> : <span className="badge">Answered: {step.answer}</span>}
          </div>
          <p className="claim">{step.question}</p>
          <p className="reason">{step.why}</p>
        </>
      );
    case "tool_call":
      return (
        <>
          <div className="timeline-head">
            <h3>
              <code>{step.tool}</code>
            </h3>
          </div>
          <p>{step.summary}</p>
          <details className="io">
            <summary>
              <ChevronRight size={13} className="chev" aria-hidden />
              Input and output
            </summary>
            <div className="io-grid">
              <div>
                <p className="io-label">Input</p>
                <Json value={step.input} />
              </div>
              <div>
                <p className="io-label">Output</p>
                <Json value={step.output} />
              </div>
            </div>
          </details>
        </>
      );
    case "verifier":
      return (
        <>
          <div className="timeline-head">
            <h3>Checked a claim</h3>
            <VerdictBadge verdict={step.verdict} />
            {step.section_id ? <SectionChip id={step.section_id} sections={sections} /> : <span className="chip">no section id</span>}
          </div>
          <p className="claim">{step.claim}</p>
          <p className="reason">{step.reason}</p>
        </>
      );
    case "draft":
      return (
        <>
          <div className="timeline-head">
            <h3>Drafted a message for approval</h3>
            <span className="badge badge-blue">{step.tone}</span>
          </div>
          <p>Draft {step.draft_id} waits for the tenant to approve it.</p>
        </>
      );
    case "approval":
      return (
        <>
          <div className="timeline-head">
            <h3>Tenant approved draft {step.draft_id}</h3>
            <span className="badge badge-green">Approved</span>
          </div>
          <p>{step.follow_up_date ? `Follow-up recorded for ${step.follow_up_date}. Not delivered automatically.` : "No follow-up recorded."}</p>
        </>
      );
    case "landlord_offer":
      return (
        <>
          <div className="timeline-head">
            <h3>
              Round {step.round}: {PERSONA_LABEL[step.persona]} made {step.offers.length} {step.offers.length === 1 ? "offer" : "offers"}
            </h3>
          </div>
          <ul>
            {step.offers.map((o) => (
              <li key={o.move_id}>
                <span className="mono">{o.clause_id}</span> {termsText(o.terms)}
              </li>
            ))}
          </ul>
        </>
      );
    case "tenant_decision":
      return (
        <>
          <div className="timeline-head">
            <h3>Round {step.round}: tenant agent decided</h3>
            {step.fallback ? <span className="badge badge-amber">rule-based</span> : <span className="badge">model {(step.model_ms / 1000).toFixed(1)} s</span>}
          </div>
          <ul>
            {step.decisions.map((d) => (
              <li key={d.clause_id}>
                <span className="mono">{d.clause_id}</span> {d.decision}
                {d.limit_override && " (limit enforced)"} · {d.verdict}
                {d.section_id && <> · <SectionChip id={d.section_id} sections={sections} /></>}
              </li>
            ))}
          </ul>
          {step.error && <p className="reason">Model step failed: {step.error}. Rule-based decisions instead.</p>}
        </>
      );
    case "negotiation_settled":
      return (
        <>
          <div className="timeline-head">
            <h3>Negotiation {step.open_clauses.length ? "stalled" : "settled"}</h3>
            <span className={`badge ${step.open_clauses.length ? "badge-amber" : "badge-green"}`}>
              {step.settled_clauses.length} agreed · {step.open_clauses.length} open
            </span>
          </div>
          <p>The agreed terms wait for the tenant&apos;s approval; open clauses keep the tenant&apos;s ask.</p>
        </>
      );
    case "needs_itemisation":
      return (
        <>
          <div className="timeline-head">
            <h3>Asked for the itemised list first</h3>
            <SectionChip id="ICA-74" sections={sections} />
          </div>
          <p>
            {inr(step.withheld_inr)} withheld{step.deposit_inr ? ` from a deposit of ${inr(step.deposit_inr)}` : ""}, and {step.reason}. No item is disputed
            until the landlord itemises it.
          </p>
        </>
      );
  }
}

/** The agent's decision trace. If a step is not here, it did not happen (CLAUDE.md, agent contract). */
export function Trace({ trace, sections }: { trace: TraceStep[]; sections: Record<string, Section> }) {
  return (
    <ol className="timeline">
      {trace.map((step) => (
        <li key={step.index} id={`step-${step.index}`} className={`timeline-item ${step.type === "verifier" && step.verdict === "blocked" ? "is-blocked" : ""}`}>
          <span className={`timeline-badge ${badgeClass(step)}`}>
            <StepIcon step={step} />
          </span>
          <div className="timeline-body">
            <div className="timeline-kind">
              {String(step.index + 1).padStart(2, "0")} · {KIND[step.type]}
              {step.at && ` · ${time(step.at)}`}
            </div>
            <StepBody step={step} sections={sections} />
          </div>
        </li>
      ))}
    </ol>
  );
}
