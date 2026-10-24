"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createMoveout, loadMoveoutInput } from "@/lib/api";
import { inr } from "@/lib/format";
import type { MoveoutInput } from "@/lib/types";
import moveout from "@/stubs/moveout.json";

const CATEGORIES = [
  { value: "painting_or_cleaning_fixed", label: "Painting or cleaning" },
  { value: "wear_and_tear", label: "Wear and tear" },
  { value: "damage", label: "Damage or repair" },
];

interface Row {
  label: string;
  category: string;
  clause_ref: string;
  amount: string;
}

const EMPTY: Row = { label: "", category: "damage", clause_ref: "", amount: "" };

/** Once the landlord sends the itemised list, enter it here: the normal item-by-item check runs on it. */
export function ItemiseForm({ reviewId, withheld }: { reviewId: string; withheld: number }) {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([{ ...EMPTY, label: "painting", category: "painting_or_cleaning_fixed", clause_ref: "C3" }, { ...EMPTY }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const total = rows.reduce((sum, r) => sum + (Number(r.amount) || 0), 0);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const items = rows.filter((r) => r.label.trim() || r.amount);
    if (!items.length || items.some((r) => !r.label.trim() || !(Number(r.amount) > 0))) return setError("Give every item a name and an amount.");
    const original = loadMoveoutInput(reviewId) ?? ({ ...moveout.sample_request, deposit_inr: moveout.deposit_inr, language: "en" } as MoveoutInput);
    setBusy(true);
    setError(null);
    try {
      const id = await createMoveout({
        ...original,
        claimed_text: null,
        deductions: items.map((r) => ({ label: r.label.trim(), category: r.category, clause_ref: r.clause_ref.trim(), amount_inr: Math.round(Number(r.amount)), evidence_ids: [] })),
      });
      router.push(`/moveout/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check the itemised deductions.");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate>
      <figure className="fig-table">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Type</th>
                <th>Clause</th>
                <th className="num">Amount (₹)</th>
                <th aria-label="Remove" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>
                    <label className="sr-only" htmlFor={`item-${i}`}>
                      Item {i + 1}
                    </label>
                    <input id={`item-${i}`} type="text" value={r.label} placeholder="e.g. repainting" onChange={(e) => update(i, { label: e.target.value })} />
                  </td>
                  <td>
                    <label className="sr-only" htmlFor={`type-${i}`}>
                      Type of item {i + 1}
                    </label>
                    <select id={`type-${i}`} value={r.category} onChange={(e) => update(i, { category: e.target.value })}>
                      {CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <label className="sr-only" htmlFor={`clause-${i}`}>
                      Clause for item {i + 1}
                    </label>
                    <input id={`clause-${i}`} type="text" value={r.clause_ref} placeholder="e.g. C4" onChange={(e) => update(i, { clause_ref: e.target.value })} style={{ maxWidth: 72 }} />
                  </td>
                  <td className="num">
                    <label className="sr-only" htmlFor={`amount-${i}`}>
                      Amount for item {i + 1}
                    </label>
                    <input id={`amount-${i}`} type="number" inputMode="numeric" min={0} value={r.amount} onChange={(e) => update(i, { amount: e.target.value })} style={{ maxWidth: 120, textAlign: "right" }} />
                  </td>
                  <td>
                    {rows.length > 1 && (
                      <button type="button" className="btn btn-sm" aria-label={`Remove item ${i + 1}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                        <X size={14} aria-hidden />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>Itemised total (withheld: {inr(withheld)})</td>
                <td className="num">{inr(total)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
        <figcaption>The landlord&apos;s itemised list. Each item is then checked against the agreement and the move-in checklist.</figcaption>
      </figure>
      <div className="form-actions">
        <button type="button" className="btn btn-sm" onClick={() => setRows([...rows, { ...EMPTY }])}>
          <Plus size={14} aria-hidden /> Add an item
        </button>
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Checking…" : "Check the itemised deductions"}
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
