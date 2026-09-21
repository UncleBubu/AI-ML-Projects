import { useState } from "react";
import { getSummary } from "../api/reports";
import type { Range } from "../api/reports";
import { formatNaira } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { useCallback } from "react";

// Reads ONLY from GET /reports/summary - nothing is computed in the browser.
// `refreshKey` changes whenever invoices/expenses change, re-fetching the numbers.
export function SummaryPanel({ refreshKey }: { refreshKey: number }) {
  const [range, setRange] = useState<Range>("week");
  // Re-create the loader when range OR refreshKey changes => useAsync refetches.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loader = useCallback(() => getSummary(range), [range, refreshKey]);
  const { data: s, error, loading } = useAsync(loader);

  return (
    <div className="card">
      <div className="row between">
        <h2>Summary ({range === "week" ? "this week" : "this month"}, WAT)</h2>
        <select value={range} onChange={(e) => setRange(e.target.value as Range)} aria-label="Range">
          <option value="week">This week</option>
          <option value="month">This month</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && !s && <p className="muted">Loading...</p>}
      {s && (
        <div className="stats">
          <Stat label="Money in" value={formatNaira(s.revenue)} />
          <Stat label="Money out" value={formatNaira(s.expenses)} />
          <Stat label={s.net_cash >= 0 ? "Net (green)" : "Net (red)"} value={formatNaira(s.net_cash)} tone={s.net_cash >= 0 ? "good" : "bad"} />
          <Stat label="Avg invoice" value={s.average_invoice_value == null ? "-" : formatNaira(s.average_invoice_value)} />
          <Stat label="Invoices paid" value={String(s.invoices_paid)} />
          <Stat label="Overdue now" value={`${s.overdue_now.count} (${formatNaira(s.overdue_now.amount)})`} tone={s.overdue_now.count ? "bad" : undefined} />
        </div>
      )}
      {s && s.customer_payment_speed.length > 0 && (
        <p className="muted">
          Payment speed: {s.customer_payment_speed.map((c) => `${c.customer_name} ${c.avg_days_to_payment}d`).join(" | ")}
        </p>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" | undefined }) {
  return <div className={`stat ${tone ?? ""}`}><div className="muted">{label}</div><div className="value">{value}</div></div>;
}
