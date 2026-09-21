import { useState } from "react";
import { remindCustomer, retryPaymentLink, verifyInvoice, voidInvoice } from "../api/invoices";
import type { Invoice, ReminderResult } from "../api/invoices";
import { errorMessage, formatDate, formatNaira } from "../lib/format";

const describe = (r: ReminderResult) =>
  r.status === "sent" ? `${r.channel} sent to ${r.to}` : `${r.channel} ${r.status}${r.detail ? ` (${r.detail})` : ""}`;

export function InvoiceList({ invoices, onChanged }: { invoices: Invoice[]; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function act(id: string, fn: () => Promise<unknown>, okMessage: (r: unknown) => string) {
    setBusy(id); setMessage(null);
    try { setMessage(okMessage(await fn())); onChanged(); }
    catch (err) { setMessage(errorMessage(err)); }
    finally { setBusy(null); }
  }

  // Customer-facing, so we confirm exactly WHO will be contacted before anything is sent.
  function remind(inv: Invoice) {
    const c = inv.customer;
    const to = [c?.email, c?.phone].filter(Boolean).join(" and ") || "the customer";
    if (!window.confirm(`Send a payment reminder for ${inv.invoice_number} to ${c?.name ?? "the customer"} (${to})?`)) return;
    void act(inv.id, () => remindCustomer(inv.id), (r) => (r as { results: ReminderResult[] }).results.map(describe).join("; "));
  }

  return (
    <div className="card">
      <div className="row between">
        <h2>Invoices</h2>
        <button onClick={onChanged}>Refresh</button>
      </div>
      {message && <p role="status">{message}</p>}
      {invoices.length === 0 ? <p className="muted">No invoices yet.</p> : (
        <table>
          <thead><tr><th>No.</th><th>Customer</th><th>Due</th><th>Total</th><th>Status</th><th /></tr></thead>
          <tbody>
            {invoices.map((inv) => {
              const unpaid = inv.status === "sent" || inv.status === "overdue";
              return (
                <tr key={inv.id}>
                  <td data-label="No.">{inv.invoice_number}</td>
                  <td data-label="Customer">{inv.customer?.name ?? "-"}</td>
                  <td data-label="Due">{formatDate(inv.due_date)}</td>
                  <td data-label="Total">{formatNaira(inv.total_amount)}</td>
                  <td data-label="Status"><span className={`badge ${inv.status}`}>{inv.status}</span></td>
                  <td className="actions">
                    {inv.checkout_url && inv.status !== "paid" && inv.status !== "void" && (
                      <a href={inv.checkout_url} target="_blank" rel="noreferrer">Pay link</a>
                    )}
                    {unpaid && (
                      <>
                        <button className="primary" disabled={busy === inv.id} onClick={() => remind(inv)}>Remind customer</button>
                        <button disabled={busy === inv.id}
                          onClick={() => act(inv.id, () => verifyInvoice(inv.id), (r) => `Check result: ${(r as { result: string }).result}`)}>
                          Check payment
                        </button>
                      </>
                    )}
                    {inv.status === "draft" && (
                      <button disabled={busy === inv.id}
                        onClick={() => act(inv.id, () => retryPaymentLink(inv.id), () => "Payment link created")}>
                        Retry payment link
                      </button>
                    )}
                    {(inv.status === "draft" || unpaid) && inv.amount_paid === 0 && (
                      <button disabled={busy === inv.id}
                        onClick={() => window.confirm(`Void ${inv.invoice_number}? This cannot be undone.`) &&
                          act(inv.id, () => voidInvoice(inv.id), () => `${inv.invoice_number} voided`)}>
                        Void
                      </button>
                    )}
                    {inv.last_customer_reminder_at && (
                      <span className="muted">Reminded {formatDate(inv.last_customer_reminder_at)}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
