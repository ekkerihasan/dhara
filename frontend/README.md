# Dhara AI frontend

Next.js (App Router, TypeScript, Tailwind) client for the Dhara AI backend. Each run is rendered as an engineering-style report: numbered sections, captioned tables, and a margin table of contents.

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run demo       # production build and start, for screen sharing
```

| Route | What it shows |
|---|---|
| `/` | Upload a PDF or paste the agreement text, plus the facts form (rent, deposit, built year, local body, use, EN/KN). |
| `/review/[id]` | Governing law, unfair clauses with money at risk, counter-proposal (EN/KN) with approve, citation check, decision trace. Pauses with a question card when the run is `needs_input`. |
| `/moveout/[id]` | Flow 2 preview: move-in evidence, claimed deductions with verdicts, next formal step. |

## Stubs

`NEXT_PUBLIC_USE_STUBS` defaults to on, so every screen works before the backend does: `lib/api.ts` answers from `stubs/blr_flat.json` and `stubs/moveout.json`. Try `/review/blr_flat`, or submit the form with the built year blank to see the agent stop and ask. Set `NEXT_PUBLIC_USE_STUBS=false` and `NEXT_PUBLIC_API_URL` to use the live API (BUILD.md endpoints).

`lib/types.ts` mirrors `backend/models.py`. Change both together.

## Credits

Geist and Geist Mono (Vercel, OFL-1.1), Noto Sans Kannada (Google, OFL-1.1), Lucide icons (ISC).

## Browser demo

1. Open a fresh tab at `/`. Press **Use the sample agreement**, leave **Year built** blank, and press **Review the agreement**. The run pauses with the question card (`needs_input`).
2. Answer `2019`. The full report opens with the agent-at-a-glance strip; each item jumps to that step in the trace.
3. In **Citation check**, the two red rows are the blocked claims: the Model Tenancy Act two-month cap (wrong law) and an uncited 30-day refund claim.
4. In **Decision trace**, walk through the plan, the question, the tool calls (expand **Input and output**), the verifier steps and the draft.
5. Optional: switch the counter-proposal to ಕನ್ನಡ and press **Approve and send** to show the follow-up date.

Stub state lives in `sessionStorage`, so a new tab starts the demo fresh. Opening `/review/blr_flat` directly shows the completed run.
