"use client";

import { Construction, Info, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { approveMoveout, getMoveout } from "@/lib/api";
import { date, inr, STATUS_LABEL } from "@/lib/format";
import type { MoveoutRun } from "@/lib/types";
import { DocFooter } from "./DocFooter";
import { DraftPanel } from "./DraftPanel";
import { SectionChips } from "./SectionChip";
import { Toc } from "./Toc";

const TOC = [
  { id: "checklist", title: "Move-in evidence" },
  { id: "deductions", title: "Claimed deductions" },
  { id: "challenge", title: "Challenge" },
  { id: "next", title: "Next formal step" },
];

const POLL_MS = 1500;

/** Flow 2 report: verdicts per deduction against the move-in checklist, the challenge to approve, the formal route. */
export function MoveoutDocument({ id }: { id: string }) {
  const [run, setRun] = useState<MoveoutRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getMoveout(id)
      .then(setRun)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the move-out."));
  }, [id]);

  useEffect(load, [load]);

  // Live mode: keep polling while the agent works.
  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [run?.status, load]);

  if (error || !run) {
    return (
      <main className="doc">
        <div />
        <div className="doc-main">
          {error ? (
            <div className="callout callout-danger">
              <TriangleAlert size={16} aria-hidden />
              <p>{error}</p>
            </div>
          ) : (
            <div aria-busy="true">
              <div className="skeleton" style={{ width: "30%" }} />
              <div className="skeleton" style={{ width: "80%", height: 36 }} />
            </div>
          )}
        </div>
      </main>
    );
  }

  const claimed = run.deductions.reduce((s, d) => s + d.claimed_inr, 0);
  const disputed = run.deductions.filter((d) => d.verdict === "disputed").reduce((s, d) => s + d.claimed_inr, 0);

  return (
    <main className="doc">
      <Toc items={TOC} />
      <article className="doc-main">
        <p className="kicker">
          Move-out report · <span className="mono">{run.id}</span>
          <span className="badge badge-amber">{STATUS_LABEL[run.status]}</span>
        </p>
        <h1 className="doc-title">{run.title}</h1>
        <p className="doc-subtitle">
          Each deduction the landlord claimed, checked against the agreement and the dated move-in evidence, with the formal route if the deposit is
          not returned.
        </p>
        {!run.live && (
          <div className="callout callout-warning">
            <Construction size={16} aria-hidden />
            <p>
              <strong>Sample data.</strong> This report is precomputed for the sample move-out; with the backend running, the agent checks your own
              deductions.
            </p>
          </div>
        )}
        {run.status === "running" && (
          <div className="callout">
            <Info size={16} aria-hidden />
            <p>The agent is checking each deduction against the agreement and the move-in checklist. This takes up to a minute.</p>
          </div>
        )}

        <div className="stats">
          <div className="stat">
            <div className="stat-value">{inr(run.deposit_inr)}</div>
            <div className="stat-label">Deposit paid</div>
          </div>
          <div className="stat">
            <div className="stat-value">{inr(claimed)}</div>
            <div className="stat-label">Deductions claimed</div>
          </div>
          <div className="stat is-danger">
            <div className="stat-value">{inr(disputed)}</div>
            <div className="stat-label">Disputed with a cited reason</div>
          </div>
        </div>

        <section className="section" id="checklist">
          <h2>Move-in evidence</h2>
          <p>Dated entries recorded at move-in and at handover. The agent compares each claimed deduction against these.</p>
          <figure className="fig-table">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Item</th>
                    <th>Condition</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {run.checklist.map((c) => (
                    <tr key={`${c.date}-${c.item}`}>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {c.id && <span className="mono">{c.id} · </span>}
                        {date(c.date)}
                      </td>
                      <td>{c.item}</td>
                      <td>{c.condition}</td>
                      <td className="dim">{c.evidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <figcaption>Move-in checklist and handover notes.</figcaption>
          </figure>
        </section>

        <section className="section" id="deductions">
          <h2>Claimed deductions</h2>
          <figure className="fig-table">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Deduction</th>
                    <th className="num">Claimed</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {run.deductions.map((d) => (
                    <tr key={d.label} className={d.verdict === "disputed" ? "is-blocked" : undefined}>
                      <td>
                        <strong style={{ fontWeight: 600 }}>{d.label}</strong>
                        <div className="dim" style={{ fontSize: 13, margin: "4px 0 8px" }}>
                          {d.reason}
                        </div>
                        <span className="chips">
                          <SectionChips ids={d.section_ids} sections={run.sections} />
                          {(d.evidence_ids ?? []).map((e) => (
                            <span key={e} className="chip">
                              evidence {e}
                            </span>
                          ))}
                        </span>
                      </td>
                      <td className="num">{inr(d.claimed_inr)}</td>
                      <td>
                        {d.verdict ? (
                          <span className={`badge ${d.verdict === "allowed" ? "badge-green" : "badge-red"}`}>{d.verdict}</span>
                        ) : (
                          <span className="badge">checking</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td>Disputed</td>
                    <td className="num">{inr(disputed)}</td>
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
            <figcaption>Deductions claimed by the landlord and the agent&apos;s verdict on each.</figcaption>
          </figure>
        </section>

        <section className="section" id="challenge">
          <h2>Challenge</h2>
          {run.drafts?.[0] ? (
            <>
              <p>Written from the disputed deductions. Approving records a follow-up date; Dhara never sends anything itself.</p>
              <DraftPanel
                draft={run.drafts[0]}
                initialLanguage={run.facts.language}
                approval={run.follow_up_date ? { index: 0, at: "", type: "approval", draft_id: run.drafts[0].id, approved: true, follow_up_date: run.follow_up_date } : null}
                onApprove={async () => {
                  await approveMoveout(run.id);
                  load();
                }}
              />
            </>
          ) : (
            <p>{run.live ? "The challenge appears here when the agent finishes." : "In live mode, the agent drafts the challenge here in English and Kannada."}</p>
          )}
        </section>

        <section className="section" id="next">
          <h2>Next formal step</h2>
          <p>In order. The agent never suggests a police complaint for a deposit dispute.</p>
          <ol className="box-list">
            {run.next_steps.map((s, i) => (
              <li key={s.title} className="box-row">
                <span className="step">{i + 1}</span>
                <div>
                  <p className="box-row-title" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {s.title}
                    {s.certainty === "uncertain" && <span className="badge badge-amber">uncertain</span>}
                  </p>
                  <p className="box-row-text">{s.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <DocFooter notice={run.notice} />
      </article>
    </main>
  );
}
