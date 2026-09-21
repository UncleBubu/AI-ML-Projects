import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabaseClient";
import { listInvoices, listOverdue } from "./api/invoices";
import { Brand } from "./components/Brand";
import { InvoiceForm } from "./components/InvoiceForm";
import { InvoiceList } from "./components/InvoiceList";
import { ExpenseSection } from "./components/ExpenseSection";
import { SummaryPanel } from "./components/SummaryPanel";
import { OverdueBanner } from "./components/OverdueBanner";
import { AskPanel } from "./components/AskPanel";
import { InsightsPanel } from "./components/InsightsPanel";
import { errorMessage } from "./lib/format";
import { useAsync } from "./lib/useAsync";

type Tab = "invoices" | "expenses";

function Dashboard({ session }: { session: Session }) {
  const [tab, setTab] = useState<Tab>("invoices");
  // Bumped whenever money-affecting data changes, so the summary re-fetches.
  const [refreshKey, setRefreshKey] = useState(0);
  const invoices = useAsync(listInvoices);
  const overdue = useAsync(listOverdue);

  const refreshAll = useCallback(() => {
    void invoices.reload();
    void overdue.reload();
    setRefreshKey((k) => k + 1);
  }, [invoices, overdue]);

  return (
    <>
      {/* Full-width brand bar (styling only). The page content below is unchanged. */}
      <header className="topbar">
        <div className="topbar-inner">
          <Brand />
          <div className="topbar-user">
            <span className="topbar-email">{session.user.email}</span>
            <button onClick={() => supabase.auth.signOut()}>Log out</button>
          </div>
        </div>
      </header>

      <div className="page">
        {overdue.data && <OverdueBanner overdue={overdue.data} onRan={refreshAll} />}
        <SummaryPanel refreshKey={refreshKey} />
        <div className="two-col">
          <AskPanel />
          <InsightsPanel />
        </div>

        <nav className="tabs">
          <button className={tab === "invoices" ? "active" : ""} onClick={() => setTab("invoices")}>Invoices</button>
          <button className={tab === "expenses" ? "active" : ""} onClick={() => setTab("expenses")}>Expenses</button>
        </nav>

        {tab === "invoices" && (
          <>
            <InvoiceForm onCreated={refreshAll} />
            {invoices.error && <p className="error">{invoices.error}</p>}
            <InvoiceList invoices={invoices.data ?? []} onChanged={refreshAll} />
          </>
        )}
        {tab === "expenses" && <ExpenseSection onChanged={() => setRefreshKey((k) => k + 1)} />}
      </div>
    </>
  );
}

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function submit(e: FormEvent, mode: "login" | "signup") {
    e.preventDefault();
    setMessage(null);
    const { error } = mode === "login"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    if (error) setMessage(errorMessage(error));
    else if (mode === "signup") setMessage("Signed up. If email confirmation is on, check your inbox, then log in.");
  }

  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={(e) => submit(e, "login")}>
        <Brand stacked />
        <p className="auth-tagline">Invoicing and cash flow, made simple.</p>
        <input aria-label="Email" placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input aria-label="Password" placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
        <div className="row">
          <button type="submit">Log In</button>
          <button type="button" onClick={(e) => submit(e, "signup")}>Sign Up</button>
        </div>
        {message && <p role="status">{message}</p>}
      </form>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => listener.subscription.unsubscribe();
  }, []);

  if (!ready) return null; // avoid flashing the login form while the session loads
  return session ? <Dashboard session={session} /> : <Login />;
}
