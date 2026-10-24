import type { TraceStep } from "@/lib/types";

interface Item {
  kind: string;
  value: string;
  href: string;
  tone?: "safe" | "danger";
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** The agent loop in one row, counted from the trace. Each item jumps to its first step in the trace. */
export function AgentGlance({ trace }: { trace: TraceStep[] }) {
  const first = (match: (s: TraceStep) => boolean) => {
    const step = trace.find(match);
    return step ? `#step-${step.index}` : "#trace";
  };
  const count = (match: (s: TraceStep) => boolean) => trace.filter(match).length;

  const questions = count((s) => s.type === "question");
  const tools = count((s) => s.type === "tool_call");
  const checked = count((s) => s.type === "verifier");
  const blocked = count((s) => s.type === "verifier" && s.verdict === "blocked");
  const drafts = count((s) => s.type === "draft");
  const approved = trace.some((s) => s.type === "approval" && s.approved);

  const items: Item[] = [
    { kind: "Plan", value: "Planned", href: first((s) => s.type === "plan") },
    { kind: "Ask", value: plural(questions, "question"), href: first((s) => s.type === "question") },
    { kind: "Act", value: plural(tools, "tool"), href: first((s) => s.type === "tool_call") },
    { kind: "Verify", value: plural(checked, "claim"), href: first((s) => s.type === "verifier"), tone: "safe" },
    { kind: "Blocked", value: plural(blocked, "claim"), href: first((s) => s.type === "verifier" && s.verdict === "blocked"), tone: blocked ? "danger" : undefined },
    { kind: "Draft", value: plural(drafts, "message"), href: first((s) => s.type === "draft") },
    { kind: "Approve", value: approved ? "Sent" : "Waiting", href: approved ? first((s) => s.type === "approval") : "#draft", tone: approved ? "safe" : undefined },
  ];

  return (
    <nav aria-label="What the agent did">
      <ol className="glance">
        {items.map((item) => (
          <li key={item.kind}>
            <a href={item.href} className={item.tone ? `is-${item.tone}` : undefined}>
              <span className="glance-kind">{item.kind}</span>
              <span className="glance-value">{item.value}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
