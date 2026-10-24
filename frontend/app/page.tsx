import { DocFooter } from "@/components/DocFooter";
import { IntakeForm } from "@/components/IntakeForm";
import { Toc } from "@/components/Toc";
import { Topbar } from "@/components/Topbar";

const TOC = [
  { id: "agreement", title: "The agreement" },
  { id: "facts", title: "Facts about the rental" },
  { id: "how", title: "What the agent does" },
];

const STEPS = [
  { title: "Plan", text: "Lists the tool calls it intends to make before making any." },
  { title: "Ask", text: "If a fact that decides the governing law is missing, it stops and asks you instead of guessing." },
  { title: "Act", text: "Reads the agreement, runs the Karnataka Rent Act test, looks up sections, prices each clause in rupees." },
  { title: "Verify", text: "Every legal claim must cite a section that applies in Karnataka. Wrong-law and uncited claims are blocked." },
  { title: "Draft and wait", text: "Writes the counter-proposal in English or Kannada. Nothing is sent until you approve it." },
];

export default function Home() {
  return (
    <>
      <Topbar current="new" />
      <main className="doc">
        <Toc items={TOC} />
        <article className="doc-main">
          <p className="kicker">Karnataka · Agentic tenancy copilot</p>
          <h1 className="doc-title">Review a rental agreement before you sign it</h1>
          <p className="doc-subtitle">
            Dhara works out which law actually governs your rental, prices every unfair clause in rupees, and drafts the message to your landlord.
            You approve every message it sends.
          </p>
          <div className="abstract">
            <h2>Why this exists</h2>
            <p>
              Most modern flats in Bengaluru fall outside the Karnataka Rent Act, and Karnataka has not adopted the Model Tenancy Act. Advice that
              quotes a two-month deposit cap is wrong here. Dhara cites only sections that apply, and shows every step it took.
            </p>
          </div>

          <IntakeForm />

          <section className="section" id="how">
            <h2>What the agent does</h2>
            <p>Each step below appears in the decision trace of your report. If it is not in the trace, it did not happen.</p>
            <ol className="box-list">
              {STEPS.map((s, i) => (
                <li key={s.title} className="box-row">
                  <span className="step">{i + 1}</span>
                  <div>
                    <p className="box-row-title">{s.title}</p>
                    <p className="box-row-text">{s.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <DocFooter />
        </article>
      </main>
    </>
  );
}
