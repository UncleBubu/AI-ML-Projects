-- ============================================================================
-- Day 9: RLS hardening (found while writing the isolation test)
-- ============================================================================

-- 1) `profiles` had NO row level security. Anyone holding the public anon key
--    could read every user's email through the REST API. Lock it to "own row".
alter table public.profiles enable row level security;
create policy "Users can view their own profile"
  on public.profiles for select
  using (id = auth.uid());

-- 2) Browsers must never WRITE financial data directly. With the Day 1 INSERT
--    policies, a logged-in user could POST straight to /rest/v1/invoice with the
--    public anon key and choose their own total_amount, skipping every
--    server-side rule (server-computed totals, invoice numbering, Paystack).
--    All writes go through our backend (service role, which bypasses RLS), so
--    the client-side INSERT policies are removed: RLS becomes read-only for users.
drop policy if exists "Owners can insert their business"            on public.business;
drop policy if exists "Owners can insert their customers"           on public.customer;
drop policy if exists "Owners can insert their invoices"            on public.invoice;
drop policy if exists "Owners can insert their invoice line items"  on public.invoice_line_item;
drop policy if exists "Owners can insert their expenses"            on public.expense;

-- 3) Belt and braces: users only ever need SELECT from the browser.
revoke insert, update, delete on
  public.business, public.customer, public.invoice, public.invoice_line_item,
  public.transaction, public.expense, public.reminder_log, public.profiles
from anon, authenticated;
