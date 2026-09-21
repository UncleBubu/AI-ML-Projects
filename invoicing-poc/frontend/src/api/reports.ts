import { authorizedFetch } from "./client";

export type Range = "week" | "month";

export interface Summary {
  range: Range;
  timezone: string;
  revenue: number;
  expenses: number;
  net_cash: number;
  expenses_by_category: Record<string, number>;
  invoices_issued: number;
  average_invoice_value: number | null;
  invoices_paid: number;
  overdue_now: { count: number; amount: number };
  outstanding_now: { count: number; amount: number };
  customer_payment_speed: { customer_id: string; customer_name: string; paid_invoices: number; avg_days_to_payment: number }[];
}

export const getSummary = (range: Range) => authorizedFetch<Summary>(`/reports/summary?range=${range}`);
