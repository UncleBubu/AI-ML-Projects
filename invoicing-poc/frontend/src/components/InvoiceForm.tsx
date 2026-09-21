import { useState } from "react";
import type { FormEvent } from "react";
import { createCustomer, createInvoice, listCustomers } from "../api/invoices";
import type { Invoice, LineItemInput } from "../api/invoices";
import { errorMessage, formatNaira } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const emptyLineItem: LineItemInput = { description: "", quantity: 1, unit_price: 0 };
const NEW = "__new__";

export function InvoiceForm({ onCreated }: { onCreated: () => void }) {
  const customers = useAsync(listCustomers);
  const [customerId, setCustomerId] = useState<string>(NEW);
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [lineItems, setLineItems] = useState<LineItemInput[]>([{ ...emptyLineItem }]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Live total for display only - the server recomputes it and ignores this one.
  const total = lineItems.reduce((sum, i) => sum + i.quantity * i.unit_price, 0);

  const updateLineItem = (index: number, patch: Partial<LineItemInput>) =>
    setLineItems((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // Existing customer: use its id. New: create-or-find by email first.
      const id = customerId === NEW
        ? (await createCustomer({ name: customerName, email: customerEmail, ...(customerPhone.trim() ? { phone: customerPhone.trim() } : {}) })).id
        : customerId;
      const invoice = await createInvoice({ customer_id: id, due_date: dueDate, line_items: lineItems });
      setResult(invoice);
      onCreated();
      void customers.reload();
    } catch (err) {
      setError(errorMessage(err));
      onCreated(); // a 502 still saved a draft - refresh the list so it shows
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setResult(null); setLineItems([{ ...emptyLineItem }]); setDueDate("");
    setCustomerName(""); setCustomerEmail(""); setCustomerPhone(""); setCustomerId(NEW);
  }

  if (result) {
    return (
      <div className="card">
        <h2>Invoice {result.invoice_number} created</h2>
        <p>Total: {formatNaira(result.total_amount)}</p>
        {result.checkout_url && (
          <p><a href={result.checkout_url} target="_blank" rel="noreferrer">Open sandbox payment link</a></p>
        )}
        <button onClick={reset}>Create another</button>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>New invoice</h2>

      <label>Customer
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
          <option value={NEW}>+ New customer</option>
          {customers.data?.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.email})</option>)}
        </select>
      </label>

      {customerId === NEW && (
        <div className="row">
          <input placeholder="Customer name" value={customerName} onChange={(e) => setCustomerName(e.target.value)} required />
          <input type="email" placeholder="Customer email" value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} required />
          <input type="tel" placeholder="Phone (for SMS reminders, e.g. 0801 234 5678)" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
        </div>
      )}

      <label>Due date
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />
      </label>

      <h3>Line items</h3>
      {lineItems.map((item, index) => (
        <div className="row" key={index}>
          <input placeholder="Description" value={item.description}
            onChange={(e) => updateLineItem(index, { description: e.target.value })} required />
          <input type="number" min={1} step={1} value={item.quantity} aria-label="Quantity"
            onChange={(e) => updateLineItem(index, { quantity: Number(e.target.value) })} required />
          <input type="number" min={0.01} step="0.01" value={item.unit_price} aria-label="Unit price"
            onChange={(e) => updateLineItem(index, { unit_price: Number(e.target.value) })} required />
          <span className="amount">{formatNaira(item.quantity * item.unit_price)}</span>
          {lineItems.length > 1 && (
            <button type="button" onClick={() => setLineItems((items) => items.filter((_, i) => i !== index))}>Remove</button>
          )}
        </div>
      ))}
      <button type="button" onClick={() => setLineItems((items) => [...items, { ...emptyLineItem }])}>+ Add line item</button>

      <h3>Total: {formatNaira(total)}</h3>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit" disabled={submitting}>{submitting ? "Creating..." : "Create invoice & get payment link"}</button>
    </form>
  );
}
