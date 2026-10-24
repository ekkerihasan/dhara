import { CircleCheck, CircleX } from "lucide-react";

// The chatbot lines are verbatim from one plain-model run (no tools, no checker) on the blr_flat test agreement,
// 24 Oct 2026, with the baseline prompt in env/run_eval.py. Dhara's lines are from the sample report built by the real tools.
const CLAUSE = "C2. The entire deposit is forfeited on any breach or early exit.";

const CHATBOT = [
  { said: "Governing law: Karnataka Rent Act", why: "The flat was built in 2019. The Act does not cover a building for its first 15 years." },
  { said: "“Forfeiture of entire security deposit … is unlawful under KRA-15 and ICA-74”", why: "KRA-15 is a Rent Act section, so it does not apply to this flat." },
  { said: "“Annual rent escalation of 15% exceeds the permissible 10% per annum”", why: "No law sets 10%, and it cited no section." },
];

const DHARA = [
  { said: "The Karnataka Rent Act does not apply: built in 2019, inside the 15-year exemption", ref: "s.2(3)(f)" },
  { said: "Only reasonable compensation is recoverable; forfeiting the whole deposit is a penalty", ref: "Indian Contract Act s.74" },
  { said: "At risk: ₹1,50,000. Ask: replace forfeiture with deduction of actual, itemised loss", ref: "fixed formula" },
];

/** One real clause, answered by a plain chatbot and by Dhara, so the difference is visible at a glance. */
export function ChatbotVsDhara() {
  return (
    <figure className="vs">
      <p className="vs-clause">
        <span className="badge">Clause</span> {CLAUSE}
      </p>
      <div className="vs-grid">
        <div className="panel">
          <div className="panel-head">
            <span>Plain chatbot</span>
            <span className="badge badge-red">Wrong law</span>
          </div>
          <ul className="vs-list">
            {CHATBOT.map((c) => (
              <li key={c.said}>
                <CircleX size={15} aria-hidden className="vs-icon is-bad" />
                <div>
                  <p>{c.said}</p>
                  <p className="vs-why">{c.why}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <div className="panel-head">
            <span>Dhara</span>
            <span className="badge badge-green">Sections verified</span>
          </div>
          <ul className="vs-list">
            {DHARA.map((d) => (
              <li key={d.said}>
                <CircleCheck size={15} aria-hidden className="vs-icon is-good" />
                <div>
                  <p>{d.said}</p>
                  <p className="vs-why">{d.ref}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <figcaption>
        The chatbot&apos;s words are quoted from one real run of the same model with no tools and no checker, on our Bengaluru flat test agreement.
      </figcaption>
    </figure>
  );
}
