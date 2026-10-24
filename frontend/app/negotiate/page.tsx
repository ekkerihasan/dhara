"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DocFooter } from "@/components/DocFooter";
import { negotiationRequest, type Negotiation } from "@/lib/negotiation";

export default function NegotiatePage() {
  const [run, setRun] = useState<Negotiation | null>(null);
  const [message, setMessage] = useState("Please replace blanket deposit forfeiture with documented reasonable loss, and provide evidence for cleaning deductions.");
  const [language, setLanguage] = useState("en");
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      negotiationRequest(`/${run.id}`, undefined, controller.signal)
        .then(setRun)
        .catch((err: Error) => { if (!controller.signal.aborted) setError(err.message); });
    }, 1500);
    return () => { clearInterval(timer); controller.abort(); };
  }, [run]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!approved || !message.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await negotiationRequest(run ? `/${run.id}/message` : "", {
        ...(!run ? { task_id: "pg_room", language } : {}), tenant_message: message, approved: true,
      });
      setRun(result);
      setApproved(false);
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the negotiation service.");
    } finally { setBusy(false); }
  }

  const waiting = busy || run?.status === "running";
  const finished = run?.status === "accepted" || run?.status === "exhausted";

  return <>
    <header className="topbar"><div className="topbar-inner">
      <Link className="brand" href="/">Dhara AI</Link>
      <Link className="nav-link" href="/">Back to new review</Link>
    </div></header>
    <main className="doc"><article className="doc-main" style={{ maxWidth: 900, margin: "0 auto" }}>
      <p className="kicker">Negotiation practice</p>
      <h1 className="doc-title">Try your proposal with a simulated landlord</h1>
      <p className="doc-subtitle">Practice with the PG example: ₹8,000 monthly rent, ₹16,000 refundable deposit, blanket deposit forfeiture, and a ₹3,000 cleaning charge. The landlord responds to your proposal and can negotiate for up to three rounds.</p>
      <p className="field-hint">This uses the live model. Nothing is sent to a real landlord. Acceptance is a practice outcome; verify any agreement before signing.</p>
      {run?.turns.map(turn => <section className="section" key={turn.round}>
        <h2>Round {turn.round} · {turn.decision === "accept" ? "Simulated acceptance" : turn.decision === "counter" ? "Counter-proposal" : "Proposal declined"}</h2>
        <div className="panel"><div className="panel-head">Your approved proposal</div><div className="panel-body">{turn.tenant_message}</div></div>
        <div className="panel"><div className="panel-head">Simulated landlord · model response</div>
          <div className="panel-body">{turn.statements.map((statement, index) => <p key={index}>
            {statement.text}<br /><small className="field-hint">{statement.verdict === "cited" ? `Citation checked: ${statement.section_id}` : "Negotiation statement · unverified"}</small>
          </p>)}</div>
        </div>
      </section>)}
      {run && <p role="status">{waiting ? "The simulated landlord is considering your proposal…" : run.status === "accepted" ? "The simulated landlord accepted this proposal. No real agreement was changed." : run.status === "exhausted" ? "Three practice rounds completed. Ask a qualified person to review unresolved terms." : `${run.rounds_remaining} practice rounds remaining.`}</p>}
      {run?.error && <p className="form-error" role="alert">{run.error}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {!finished && <form className="section" onSubmit={submit}>
        <div className="field"><label className="field-label" htmlFor="practice-language">Reply language</label>
          <select id="practice-language" value={language} onChange={event => setLanguage(event.target.value)} disabled={Boolean(run) || busy}>
            <option value="en">English</option><option value="kn">ಕನ್ನಡ</option>
          </select>
        </div>
        <div className="field" style={{ marginTop: 20 }}><label className="field-label" htmlFor="practice-proposal">Your {run ? "next " : ""}proposal</label>
          <textarea id="practice-proposal" rows={5} maxLength={12000} value={message} onChange={event => { setMessage(event.target.value); setApproved(false); }} disabled={waiting} required />
        </div>
        <label className="field-hint" style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} disabled={waiting} />
          I approve this proposal for the practice conversation.
        </label>
        <div className="form-actions"><button className="btn primary" type="submit" disabled={waiting || !approved || !message.trim()}>{waiting ? "Considering…" : "Submit approved proposal"}</button></div>
      </form>}
      {finished && <button className="btn" onClick={() => { setRun(null); setMessage(""); setApproved(false); setError(null); }}>Start a new practice</button>}
      <DocFooter />
    </article></main>
  </>;
}
