import { authorizedFetch } from "./client";
import type { Range } from "./reports";

export interface AskResult { answer: string; unverified_figures: string[]; as_of: string; }
export interface InsightsResult {
  observations: string[]; unverified_figures: string[]; range: Range; as_of: string;
  previous_period_has_data: boolean; cached: boolean;
}

export const ask = (question: string) =>
  authorizedFetch<AskResult>("/ask", { method: "POST", body: JSON.stringify({ question }) });

export const getInsights = (range: Range) =>
  authorizedFetch<InsightsResult>(`/insights?range=${range}`, { method: "POST" });
