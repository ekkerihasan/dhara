import { ChevronRight, CircleHelp, FileText, ListTodo, Send, ShieldCheck, Wrench } from "lucide-react";
import { time } from "@/lib/format";
import type { Section, TraceStep } from "@/lib/types";
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
              {String(step.index + 1).padStart(2, "0")} · {KIND[step.type]} · {time(step.at)}
            </div>
            <StepBody step={step} sections={sections} />
          </div>
        </li>
      ))}
    </ol>
  );
}
