import { useState } from "react";
import type { FormEvent } from "react";
import { EXPENSE_CATEGORIES, createExpense, listExpenses } from "../api/expenses";
import type { ExpenseCategory } from "../api/expenses";
import { errorMessage, formatDate, formatNaira } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export function ExpenseSection({ onChanged }: { onChanged: () => void }) {
  const { data, error: loadError, reload } = useAsync(listExpenses);
  const [category, setCategory] = useState<ExpenseCategory>("supplies");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true); setError(null);
    try {
      await createExpense({
        category, amount: Number(amount),
        ...(date ? { expense_date: date } : {}),
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      // Keep category + date (people log several in a row); clear the rest for speed.
      setAmount(""); setNote("");
      await reload();
      onChanged();
    } catch (err) { setError(errorMessage(err)); }
    finally { setSaving(false); }
  }

  return (
    <div className="card">
      <h2>Expenses</h2>
      <form onSubmit={handleSubmit}>
        <div className="row">
          <select value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)} aria-label="Category">
            {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="number" min={0.01} step="0.01" placeholder="Amount (NGN)" value={amount}
            onChange={(e) => setAmount(e.target.value)} required autoFocus />
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Date (default today)" />
          <input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          <button type="submit" disabled={saving}>{saving ? "Saving..." : "Add"}</button>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
      </form>

      {loadError && <p className="error">{loadError}</p>}
      {data && (
        <>
          <h3>Total: {formatNaira(data.total)}</h3>
          {data.expenses.length === 0 ? <p className="muted">No expenses yet.</p> : (
            <table>
              <thead><tr><th>Date</th><th>Category</th><th>Amount</th><th>Note</th></tr></thead>
              <tbody>
                {data.expenses.map((x) => (
                  <tr key={x.id}><td>{formatDate(x.expense_date)}</td><td>{x.category}</td><td>{formatNaira(x.amount)}</td><td>{x.note}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
