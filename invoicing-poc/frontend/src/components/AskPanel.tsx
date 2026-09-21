import { useState } from "react";
import type { FormEvent } from "react";
import { ask } from "../api/ai";
import type { AskResult } from "../api/ai";
import { errorMessage } from "../lib/format";

const EXAMPLES = ["How much came in this month?", "What's my average invoice value?", "Am I in the red or green this week?", "Which customers are slow payers?"];

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(q: string) {
    if (q.trim().length < 3) return;
    setLoading(true); setError(null); setResult(null);
    try { setResult(await ask(q.trim())); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  }

  return (
    <div className="card">
      <h2>Ask about your finances</h2>
      <form className="row" onSubmit={(e: FormEvent) => { e.preventDefault(); void submit(question); }}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. How much came in this month?" maxLength={500} />
        <button type="submit" className="primary" disabled={loading}>{loading ? "Thinking..." : "Ask"}</button>
      </form>
      <div className="row">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" className="chip" disabled={loading} onClick={() => { setQuestion(ex); void submit(ex); }}>{ex}</button>
        ))}
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      {result && (
        <div className="answer">
          <p>{result.answer}</p>
          {result.unverified_figures.length > 0 && (
            <p className="warn">Double-check: {result.unverified_figures.join(", ")} did not appear directly in your data (it may be a sum the assistant worked out).</p>
          )}
          <p className="muted">Based only on your recorded data as of {result.as_of.replace("T", " ")} (Lagos time).</p>
        </div>
      )}
    </div>
  );
}
