import Link from "next/link";
import { ChatbotVsDhara } from "@/components/ChatbotVsDhara";
import { DocFooter } from "@/components/DocFooter";
import { IntakeForm } from "@/components/IntakeForm";
import { Toc } from "@/components/Toc";
import { Topbar } from "@/components/Topbar";

const TOC = [
  { id: "agreement", title: "The agreement" },
  { id: "facts", title: "Facts about the rental" },
  { id: "limits", title: "Your limits" },
  { id: "how", title: "What the agent does" },
  { id: "chatbot", title: "Why not a chatbot" },
];

// Plain-model behaviour comes from the scored run in env/results/scores.json (same model, no tools, no checker).
const COMPARE = [
  { aspect: "Which law applies", chatbot: "Named the wrong governing law on all 3 test tasks; on 2 it assumed the Karnataka Rent Act protects the tenant", dhara: "Tests the building's age, rent and area against the Act's own exclusions first" },
  { aspect: "A missing fact", chatbot: "Answers anyway", dhara: "Stops and asks; \"I don't know\" leaves the law unresolved instead of guessed" },
  { aspect: "Legal citations", chatbot: "Nothing checks them; negotiating for the flat, it cited a Rent Act section (KRA-15) although the Act does not cover that flat", dhara: "A claim without a valid Karnataka section is blocked before you see it" },
  { aspect: "Rupee amounts", chatbot: "Its own arithmetic, each time", dhara: "Fixed formulas in code: the same answer every run" },
  { aspect: "Your personal data", chatbot: "The whole document goes to the model", dhara: "Aadhaar, PAN and phone numbers are removed first" },
  { aspect: "What you get", chatbot: "A chat reply", dhara: "A priced report, a letter in English, Kannada or Hindi, a follow-up date, and the move-out check" },
  { aspect: "Negotiates counter-offers against your limits and the law", chatbot: "No", dhara: "Yes" },
  { aspect: "Proof", chatbot: "None", dhara: "Every step is in the decision trace" },
];

const STEPS = [
  { title: "Plan", text: "Lists the tool calls it intends to make before making any." },
  { title: "Ask", text: "If a fact that decides the governing law is missing, it stops and asks you instead of guessing." },
  { title: "Act", text: "Reads the agreement, runs the Karnataka Rent Act test, looks up sections, prices each clause in rupees." },
  { title: "Verify", text: "Every legal claim must cite a section that applies in Karnataka. Wrong-law and uncited claims are blocked." },
  { title: "Draft and wait", text: "Writes the counter-proposal in English, Kannada or Hindi, then waits for your approval. Once approved, you can share it on WhatsApp yourself." },
  { title: "Negotiate within your limits", text: "Answers the landlord's counter-offers for up to two rounds: accept, reject or counter, each reason cited to a section. Code flips any accept past your limits to a reject; you approve the agreed terms once." },
];

export default function Home() {
  return (
    <>
      <Topbar current="new" />
      <main className="doc">
        <Toc items={TOC} />
        <article className="doc-main">
          <p className="kicker">Dhara AI · Agentic Copilot for Fair Renting · Karnataka</p>
          <h1 className="doc-title">Review a rental agreement before you sign it</h1>
          <p className="doc-subtitle">
            Dhara works out which law actually governs your rental, prices every unfair clause in rupees, and drafts the message to your landlord.
            Nothing goes out without your approval.
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

          <section className="section" id="chatbot">
            <h2>Why not just ask a chatbot</h2>
            <p>We gave the same model the same agreement and the same law file, once on its own and once inside Dhara.</p>
            <ChatbotVsDhara />
            <figure className="fig-table">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col"></th>
                      <th scope="col">Plain chatbot</th>
                      <th scope="col">Dhara</th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMPARE.map((r) => (
                      <tr key={r.aspect}>
                        <th scope="row">{r.aspect}</th>
                        <td className="dim">{r.chatbot}</td>
                        <td>{r.dhara}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <figcaption>
                Scored by plain code on three synthetic test agreements, out of 4 for the two pre-signing agreements (with negotiation) and 3 for
                the move-out: plain chatbot 3.00, 3.00 and 2.00; Dhara 3.72, 3.67 and 2.75.{" "}
                <Link href="/scores">See the evaluation</Link>.
              </figcaption>
            </figure>
          </section>

          <DocFooter />
        </article>
      </main>
    </>
  );
}
