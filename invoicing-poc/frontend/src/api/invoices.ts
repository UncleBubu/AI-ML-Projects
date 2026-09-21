import { authorizedFetch } from "./client";

export interface Customer { id: string; name: string; email: string; }
export interface LineItemInput { description: string; quantity: number; unit_price: number; }

export type InvoiceStatus = "draft" | "sent" | "paid" | "overdue" | "void";
export interface Invoice {
  id: string;
  invoice_number: string;
  status: InvoiceStatus;
  total_amount: number;
  amount_paid: number;
  due_date: string;
  checkout_url: string | null;
  customer?: { name: string; email: string; phone: string | null } | null;
  last_customer_reminder_at?: string | null;
}

export const listCustomers = () => authorizedFetch<Customer[]>("/customers");

export interface ReminderResult { channel: "email" | "sms"; status: "sent" | "failed" | "skipped"; detail?: string; to?: string; }

// Manual reminder to the CUSTOMER (email + SMS where configured / available).
export const remindCustomer = (id: string) =>
  authorizedFetch<{ results: ReminderResult[] }>(`/invoices/${id}/remind-customer`, { method: "POST", body: JSON.stringify({}) });

export const createCustomer = (input: { name: string; email: string; phone?: string }) =>
  authorizedFetch<Customer>("/customers", { method: "POST", body: JSON.stringify(input) });

export const listInvoices = () => authorizedFetch<Invoice[]>("/invoices");

export const createInvoice = (input: { customer_id: string; due_date: string; line_items: LineItemInput[] }) =>
  authorizedFetch<Invoice>("/invoices", { method: "POST", body: JSON.stringify(input) });

// Fallback for when the webhook can't reach your machine: ask Paystack directly.
export const verifyInvoice = (id: string) =>
  authorizedFetch<{ result: string }>(`/invoices/${id}/verify`, { method: "POST" });

export const retryPaymentLink = (id: string) =>
  authorizedFetch<Invoice>(`/invoices/${id}/payment-link`, { method: "POST" });

export const voidInvoice = (id: string) =>
  authorizedFetch<Invoice>(`/invoices/${id}/void`, { method: "POST" });

export interface OverdueInvoice {
  id: string; invoice_number: string; due_date: string;
  total_amount: number; amount_paid: number; customer?: { name: string } | null;
}
export const listOverdue = () => authorizedFetch<OverdueInvoice[]>("/reminders/overdue");
export const runReminders = () =>
  authorizedFetch<{ markedOverdue: number; alerted: number; delivered: string; error?: string }>("/reminders/run", { method: "POST" });
