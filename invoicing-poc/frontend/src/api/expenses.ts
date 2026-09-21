import { authorizedFetch } from "./client";

export const EXPENSE_CATEGORIES = ["rent", "transport", "supplies", "utilities", "salaries", "other"] as const;
export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number];

export interface Expense { id: string; category: ExpenseCategory; amount: number; expense_date: string; note: string | null; }

export const listExpenses = () => authorizedFetch<{ expenses: Expense[]; total: number }>("/expenses");

export const createExpense = (input: { category: ExpenseCategory; amount: number; expense_date?: string; note?: string }) =>
  authorizedFetch<Expense>("/expenses", { method: "POST", body: JSON.stringify(input) });
