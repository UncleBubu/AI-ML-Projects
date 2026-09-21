import { useState } from "react";
import { runReminders } from "../api/invoices";
import type { OverdueInvoice } from "../api/invoices";
import { errorMessage, formatNaira } from "../lib/format";

// Day 4's "visible alert": shows whenever anything is past due, no digging needed.
export function OverdueBanner({ overdue, onRan }: { overdue: OverdueInvoice[]; onRan: () => void }) {
  const [note, setNote] = useState<string | null>(null);
  if (overdue.length === 0) return null;

  const owed = overdue.reduce((s, i) => s + (i.total_amount - i.amount_paid), 0);

  async function runNow() {
    try {
      const r = await runReminders();
      setNote(r.error ? `Job error: ${r.error}` : `Marked ${r.markedOverdue} overdue, alerted ${r.alerted} (${r.delivered})`);
      onRan();
    } catch (err) { setNote(errorMessage(err)); }
  }

  return (
    <div className="banner" role="alert">
      <strong>{overdue.length} overdue invoice{overdue.length > 1 ? "s" : ""} - {formatNaira(owed)} owed.</strong>{" "}
      {overdue.slice(0, 3).map((i) => `${i.invoice_number} (${i.customer?.name ?? "?"})`).join(", ")}
      {overdue.length > 3 && ` +${overdue.length - 3} more`}
      {" "}<button onClick={runNow}>Send reminder now</button>
      {note && <div>{note}</div>}
    </div>
  );
}
