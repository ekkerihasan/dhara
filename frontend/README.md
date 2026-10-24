# Dhara AI frontend

Next.js (App Router, TypeScript, Tailwind) client for the Dhara AI backend. Each run is rendered as an engineering-style report: numbered sections, captioned tables, and a margin table of contents.

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

| Route | What it shows |
|---|---|
| `/` | Upload a PDF or paste the agreement text, plus the facts form (rent, deposit, built year, local body, use, EN/KN). |
| `/review/[id]` | Governing law, unfair clauses with money at risk, counter-proposal (EN/KN) with approve, citation check, decision trace. Pauses with a question card when the run is `needs_input`. |
| `/moveout/[id]` | Flow 2 preview: move-in evidence, claimed deductions with verdicts, next formal step. |

## Stubs

`NEXT_PUBLIC_USE_STUBS` defaults to on, so every screen works before the backend does: `lib/api.ts` answers from `stubs/blr_flat.json` and `stubs/moveout.json`. Try `/review/blr_flat`, or submit the form with the built year blank to see the agent stop and ask. Set `NEXT_PUBLIC_USE_STUBS=false` and `NEXT_PUBLIC_API_URL` to use the live API (BUILD.md Phase 5 endpoints).

`lib/types.ts` mirrors `backend/models.py`. Change both together.

## Credits

Geist and Geist Mono (Vercel, OFL-1.1), Noto Sans Kannada (Google, OFL-1.1), Lucide icons (ISC).
