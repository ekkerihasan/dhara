import { DocFooter } from "@/components/DocFooter";
import { SectionChip } from "@/components/SectionChip";
import { Toc } from "@/components/Toc";
import { Topbar } from "@/components/Topbar";
import { inr } from "@/lib/format";
import type { Section } from "@/lib/types";
import scores from "@/stubs/scores.json";

const TOC = [
  { id: "result", title: "Two runs, one task" },
  { id: "checks", title: "What the scorer checks" },
  { id: "reproduce", title: "Reproduce it" },
];

type Check = "governing_law_correct" | "money_within_500" | "citations_exist" | "wrong_law_penalty";

const CHECKS: { key: Check; label: string; tests: string }[] = [
  { key: "governing_law_correct", label: "Governing law", tests: "Did the run name the law that actually governs this flat?" },
  { key: "money_within_500", label: "Money at risk", tests: "Share of findings whose rupee amount is within Rs 500 of the formula." },
  { key: "citations_exist", label: "Citations exist", tests: "Share of cited sections that exist in the Karnataka law pack." },
  { key: "wrong_law_penalty", label: "Wrong-law penalty", tests: "Minus 1 for every section cited from a law Karnataka has not adopted." },
];

const sections = scores.sections as Record<string, Section>;
const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

/** The deterministic scorer (env/scorer.py) on the blr_flat task, from frontend/stubs/scores.json. */
export default function ScoresPage() {
  const [correct, wrong] = scores.runs;
  return (
    <>
      <Topbar current="scores" />
      <main className="doc">
        <Toc items={TOC} />
        <article className="doc-main">
          <p className="kicker">
            Evaluation · <span className="mono">{scores.task.id}</span>
          </p>
          <h1 className="doc-title">Citing the wrong law costs a point</h1>
          <p className="doc-subtitle">
            Every run is scored by plain code, with no model involved, so the same answer always gets the same score. Here is the same task scored
            twice: once correctly, once with the deposit-cap claim that circulates online.
          </p>
          <dl className="meta">
            <div>
              <dt>Task</dt>
              <dd>Bengaluru flat, 11-month agreement (synthetic)</dd>
            </div>
            <div>
              <dt>Expected findings</dt>
              <dd>{scores.task.findings}</dd>
            </div>
            <div>
              <dt>Biggest single risk</dt>
              <dd>{inr(scores.task.money_max_inr)}</dd>
            </div>
            <div>
              <dt>Forbidden sections</dt>
              <dd>
                <span className="chips">
                  {scores.task.forbidden_sections.map((id) => (
                    <SectionChip key={id} id={id} sections={sections} />
                  ))}
                </span>
              </dd>
            </div>
          </dl>

          <section className="section" id="result">
            <h2>Two runs, one task</h2>
            <div className="stats">
              <div className="stat is-safe">
                <div className="stat-value">
                  {fmt(correct.score.total)} / {scores.max_total}
                </div>
                <div className="stat-label">
                  {correct.label}: {correct.summary}
                </div>
              </div>
              <div className="stat is-danger">
                <div className="stat-value">
                  {fmt(wrong.score.total)} / {scores.max_total}
                </div>
                <div className="stat-label">
                  {wrong.label}: {wrong.summary}
                </div>
              </div>
            </div>
            {wrong.claims.map((c) => (
              <div key={c.text} className="callout callout-danger">
                <span aria-hidden>✕</span>
                <div>
                  <p>
                    <strong>&ldquo;{c.text}&rdquo;</strong>
                  </p>
                  <p style={{ marginTop: 8 }}>
                    Cites <SectionChip id={c.section_id} sections={sections} />, a Model Tenancy Act provision Karnataka has not adopted. The
                    scorer takes a point off; in a live run the verifier blocks it before it reaches the tenant.
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="section" id="checks">
            <h2>What the scorer checks</h2>
            <figure className="fig-table">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Check</th>
                      <th>What it tests</th>
                      <th className="num">{correct.label}</th>
                      <th className="num">{wrong.label}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CHECKS.map((c) => (
                      <tr key={c.key} className={wrong.score[c.key] < 0 ? "is-blocked" : undefined}>
                        <td>
                          <strong style={{ fontWeight: 600 }}>{c.label}</strong>
                        </td>
                        <td className="dim">{c.tests}</td>
                        <td className="num">{fmt(correct.score[c.key])}</td>
                        <td className="num">{fmt(wrong.score[c.key])}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={2}>Total (out of {scores.max_total})</td>
                      <td className="num">{fmt(correct.score.total)}</td>
                      <td className="num">{fmt(wrong.score.total)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              <figcaption>
                Output of <code>env/scorer.py</code> on the shipped sample runs. These are synthetic runs that show the scoring rules, not results
                from a live model.
              </figcaption>
            </figure>
          </section>

          <section className="section" id="reproduce">
            <h2>Reproduce it</h2>
            <p>From the repository root, the same numbers print in the terminal:</p>
            <pre className="codeblock">{`python -m env.scorer env/tasks/blr_flat.json env/tasks/sample_run.json
python -m env.scorer env/tasks/blr_flat.json env/tasks/sample_run_wronglaw.json`}</pre>
          </section>

          <DocFooter />
        </article>
      </main>
    </>
  );
}
