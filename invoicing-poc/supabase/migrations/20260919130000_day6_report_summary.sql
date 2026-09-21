-- ============================================================================
-- Day 6: the single source of computed financial truth
-- ============================================================================
-- Everything the dashboard AND the Claude agent will ever quote is computed
-- here, once, by the database. Nothing is re-derived in JS or by the LLM.
--
-- Period is a half-open window [p_from, p_to) - `>= from and < to` - so a
-- transaction at exactly midnight belongs to exactly one period.
-- The backend (src/lib/period.ts) decides the boundaries in Africa/Lagos time;
-- this function just receives absolute instants and never guesses a timezone.
--
-- Definitions (also documented in README_day6.md):
--   revenue        cash actually received: transactions with paid_at in window
--   expenses       expense rows with expense_date in window
--   net_cash       revenue - expenses
--   invoices_issued / average_invoice_value
--                  invoices with issue_date in window, excluding void & draft
--   invoices_paid  distinct invoices that received a payment in the window
--                  and are fully paid now
--   overdue_now / outstanding_now
--                  point-in-time snapshot (NOT windowed): what is owed today.
--                  Computed from due_date, so it is right even if the daily
--                  overdue job has not run yet.
--   customer_payment_speed
--                  all-time average days from issue to final payment, per
--                  customer (small samples per window would be noise).
create or replace function public.report_summary(
  p_business_id uuid,
  p_from        timestamptz,
  p_to          timestamptz
)
returns jsonb
language sql
stable
as $$
with
rev as (
  select coalesce(sum(t.amount), 0)::numeric(14,2) as revenue,
         count(distinct t.invoice_id)               as paying_invoices
    from public.transaction t
    join public.invoice i on i.id = t.invoice_id
   where i.business_id = p_business_id
     and t.paid_at >= p_from and t.paid_at < p_to
),
paid_now as (
  select count(distinct t.invoice_id) as invoices_paid
    from public.transaction t
    join public.invoice i on i.id = t.invoice_id
   where i.business_id = p_business_id
     and i.status = 'paid'
     and t.paid_at >= p_from and t.paid_at < p_to
),
exp as (
  select coalesce(sum(amount), 0)::numeric(14,2) as expenses
    from public.expense
   where business_id = p_business_id
     and expense_date >= p_from and expense_date < p_to
),
exp_cat as (
  select coalesce(jsonb_object_agg(category, total), '{}'::jsonb) as by_category
    from (
      select category::text as category, sum(amount)::numeric(14,2) as total
        from public.expense
       where business_id = p_business_id
         and expense_date >= p_from and expense_date < p_to
       group by category
    ) c
),
issued as (
  select count(*)                                  as invoices_issued,
         round(avg(total_amount), 2)               as average_invoice_value
    from public.invoice
   where business_id = p_business_id
     and status not in ('void', 'draft')
     and issue_date >= p_from and issue_date < p_to
),
overdue as (
  select count(*)                                                  as overdue_count,
         coalesce(sum(total_amount - amount_paid), 0)::numeric(14,2) as overdue_amount
    from public.invoice
   where business_id = p_business_id
     and status in ('sent', 'overdue')
     and due_date < now()
),
outstanding as (
  select count(*)                                                  as outstanding_count,
         coalesce(sum(total_amount - amount_paid), 0)::numeric(14,2) as outstanding_amount
    from public.invoice
   where business_id = p_business_id
     and status in ('sent', 'overdue')
),
speed as (
  select coalesce(jsonb_agg(row_to_json(s) order by s.avg_days_to_payment desc), '[]'::jsonb) as rows
    from (
      select c.id   as customer_id,
             c.name as customer_name,
             count(*)                                                        as paid_invoices,
             round(avg(extract(epoch from (p.last_paid_at - i.issue_date)) / 86400.0)::numeric, 1)
                                                                             as avg_days_to_payment
        from public.invoice i
        join public.customer c on c.id = i.customer_id
        join lateral (
          select max(t.paid_at) as last_paid_at
            from public.transaction t where t.invoice_id = i.id
        ) p on p.last_paid_at is not null
       where i.business_id = p_business_id
         and i.status = 'paid'
       group by c.id, c.name
    ) s
)
select jsonb_build_object(
  'period',            jsonb_build_object('from', p_from, 'to', p_to),
  'revenue',           rev.revenue,
  'expenses',          exp.expenses,
  'net_cash',          (rev.revenue - exp.expenses),
  'expenses_by_category', exp_cat.by_category,
  'invoices_issued',   issued.invoices_issued,
  'average_invoice_value', issued.average_invoice_value,
  'invoices_paid',     paid_now.invoices_paid,
  'overdue_now',       jsonb_build_object('count', overdue.overdue_count, 'amount', overdue.overdue_amount),
  'outstanding_now',   jsonb_build_object('count', outstanding.outstanding_count, 'amount', outstanding.outstanding_amount),
  'customer_payment_speed', speed.rows
)
from rev, paid_now, exp, exp_cat, issued, overdue, outstanding, speed;
$$;

revoke all on function public.report_summary(uuid, timestamptz, timestamptz) from public, anon, authenticated;
grant execute on function public.report_summary(uuid, timestamptz, timestamptz) to service_role;
