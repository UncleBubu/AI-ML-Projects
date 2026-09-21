import { useState } from "react";
import { getInsights } from "../api/ai";
import type { InsightsResult } from "../api/ai";
import type { Range } from "../api/reports";
import { errorMessage } from "../lib/format";

export function InsightsPanel() {
  const [range, setRange] = useState<Range>("week");
  const [result, setResult] = useState<InsightsResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function generate() {
    setLoading(true); setError(null);
    try { setResult(await getInsights(range)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  }

  return (
    <div className="card">
      <div className="row between">
        <h2>Insights</h2>
        <span className="row">
          <select value={range} onChange={(e) => { setRange(e.target.value as Range); setResult(null); }} aria-label="Insight period">
            <option value="week">This week vs last</option>
            <option value="month">This month vs last</option>
          </select>
          <button className="primary" onClick={generate} disabled={loading}>{loading ? "Analysing..." : "Generate insights"}</button>
        </span>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      {result && (
        <>
          {!result.previous_period_has_data && <p className="warn">There is no data yet for the previous period, so comparisons are limited.</p>}
          {result.observations.length === 0 ? <p className="muted">Not enough data for observations yet.</p> : (
            <ul className="insights">{result.observations.map((o, i) => <li key={i}>{o}</li>)}</ul>
          )}
          {result.unverified_figures.length > 0 && (
            <p className="warn">Double-check: {result.unverified_figures.join(", ")} did not appear directly in your data.</p>
          )}
          <p className="muted">As of {result.as_of.replace("T", " ")}{result.cached ? " (unchanged data, saved result)" : ""}</p>
        </>
      )}
      {!result && !error && <p className="muted">One click: what changed since last period, and what deserves your attention.</p>}
    </div>
  );
}
