-- ============================================================================
-- Day 8: per-customer stats for a window, so insights can COMPARE customers
-- across periods ("your best customer now pays 6 days slower").
-- ============================================================================
-- For payments received in [p_from, p_to):
--   revenue             sum of payments
--   payments            how many payments
--   avg_days_to_payment average days from invoice issue to each payment
create or replace function public.customer_period_stats(
  p_business_id uuid,
  p_from        timestamptz,
  p_to          timestamptz
)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(row_to_json(s) order by s.revenue desc), '[]'::jsonb)
  from (
    select c.id   as customer_id,
           c.name as customer_name,
           sum(t.amount)::numeric(14,2) as revenue,
           count(*)                     as payments,
           round(avg(extract(epoch from (t.paid_at - i.issue_date)) / 86400.0)::numeric, 1)
                                        as avg_days_to_payment
      from public.transaction t
      join public.invoice  i on i.id = t.invoice_id
      join public.customer c on c.id = i.customer_id
     where i.business_id = p_business_id
       and t.paid_at >= p_from and t.paid_at < p_to
     group by c.id, c.name
  ) s;
$$;

revoke all on function public.customer_period_stats(uuid, timestamptz, timestamptz) from public, anon, authenticated;
grant execute on function public.customer_period_stats(uuid, timestamptz, timestamptz) to service_role;
