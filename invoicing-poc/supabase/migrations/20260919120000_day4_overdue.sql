-- ============================================================================
-- Day 4: flip past-due invoices from 'sent' to 'overdue'
-- ============================================================================
-- One set-based UPDATE (not a loop in JS). Optionally scoped to one business so
-- the manual "run now" button only touches the caller's own data.
-- Returns how many invoices changed.
create or replace function public.mark_overdue_invoices(p_business_id uuid default null)
returns integer
language plpgsql
as $$
declare
  v_count integer;
begin
  update public.invoice
     set status = 'overdue'
   where status = 'sent'
     and due_date < now()
     and amount_paid < total_amount
     and (p_business_id is null or business_id = p_business_id);

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

revoke all on function public.mark_overdue_invoices(uuid) from public, anon, authenticated;
grant execute on function public.mark_overdue_invoices(uuid) to service_role;
