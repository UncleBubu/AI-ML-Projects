-- ============================================================================
-- Day 2 hardening + atomic invoice creation
-- ============================================================================

-- 1) One business per owner (PoC scope). This also makes "create the business
--    the first time we see this user" race-safe: a 2nd concurrent insert fails
--    with a unique violation instead of silently creating a duplicate.
create unique index if not exists business_owner_id_key on public.business(owner_id);

-- 2) Invoice numbers must be unique inside a business; a payment reference must
--    be unique everywhere (it is how the webhook finds the invoice).
create unique index if not exists invoice_business_number_key
  on public.invoice(business_id, invoice_number);
create unique index if not exists invoice_payment_reference_key
  on public.invoice(payment_reference) where payment_reference is not null;

-- 3) Indexes for the queries Days 3-6 will run constantly.
create index if not exists invoice_business_status_due_idx
  on public.invoice(business_id, status, due_date);
create index if not exists invoice_customer_idx on public.invoice(customer_id);
create index if not exists transaction_invoice_idx on public.transaction(invoice_id);
create index if not exists transaction_paid_at_idx on public.transaction(paid_at);
create index if not exists expense_business_date_idx
  on public.expense(business_id, expense_date);
create index if not exists customer_business_email_idx
  on public.customer(business_id, lower(email));

-- 4) Sanity checks on money columns. NOT VALID = enforced for new rows only, so
--    this can never fail on data you already inserted while testing Day 1.
alter table public.invoice_line_item
  add constraint line_item_positive check (quantity > 0 and unit_price > 0) not valid;
alter table public.transaction
  add constraint transaction_positive check (amount > 0) not valid;
alter table public.expense
  add constraint expense_positive check (amount > 0) not valid;
alter table public.invoice
  add constraint invoice_amounts_sane check (total_amount >= 0 and amount_paid >= 0) not valid;

-- 5) Enforce "transactions are append-only" in the database itself, not just by
--    convention: any UPDATE/DELETE on public.transaction raises an error.
create or replace function public.forbid_mutation()
returns trigger language plpgsql as $$
begin
  raise exception '% on % is not allowed: this table is append-only', tg_op, tg_table_name;
end;
$$;

drop trigger if exists transaction_append_only on public.transaction;
create trigger transaction_append_only
  before update or delete on public.transaction
  for each row execute function public.forbid_mutation();

-- 6) Atomic invoice creation. Header + line items + invoice number are written
--    in ONE transaction (a plpgsql function body is a single transaction), so a
--    failure can never leave an invoice without lines or burn an invoice number.
--    Totals are computed HERE, from the items - the client never sends a total.
create or replace function public.create_invoice(
  p_business_id uuid,
  p_customer_id uuid,
  p_due_date    timestamptz,
  p_items       jsonb   -- [{description, quantity, unit_price}, ...]
)
returns public.invoice
language plpgsql
as $$
declare
  v_seq     integer;
  v_total   numeric(12,2);
  v_invoice public.invoice;
begin
  if not exists (
    select 1 from public.customer where id = p_customer_id and business_id = p_business_id
  ) then
    raise exception 'customer_not_found' using errcode = 'P0002';
  end if;

  if jsonb_typeof(p_items) is distinct from 'array' or jsonb_array_length(p_items) = 0 then
    raise exception 'invoice needs at least one line item';
  end if;

  select coalesce(sum(round((i->>'quantity')::int * (i->>'unit_price')::numeric, 2)), 0)
    into v_total
    from jsonb_array_elements(p_items) i;

  v_seq := public.next_invoice_seq(p_business_id);

  insert into public.invoice
    (business_id, customer_id, invoice_number, issue_date, due_date, status, total_amount, amount_paid)
  values
    (p_business_id, p_customer_id, 'INV-' || lpad(v_seq::text, 4, '0'), now(), p_due_date,
     'draft', v_total, 0)
  returning * into v_invoice;

  insert into public.invoice_line_item (invoice_id, description, quantity, unit_price, line_total)
  select v_invoice.id,
         i->>'description',
         (i->>'quantity')::int,
         (i->>'unit_price')::numeric,
         round((i->>'quantity')::int * (i->>'unit_price')::numeric, 2)
    from jsonb_array_elements(p_items) i;

  return v_invoice;
end;
$$;

-- 7) SECURITY: Supabase exposes every function in `public` to anyone with the
--    anon key via /rest/v1/rpc/... unless you revoke it. These functions take a
--    business_id as an argument and bypass RLS's auth.uid() check, so they must
--    only be callable by our trusted backend (service_role).
revoke all on function public.next_invoice_seq(uuid) from public, anon, authenticated;
revoke all on function public.create_invoice(uuid, uuid, timestamptz, jsonb) from public, anon, authenticated;
grant execute on function public.next_invoice_seq(uuid) to service_role;
grant execute on function public.create_invoice(uuid, uuid, timestamptz, jsonb) to service_role;
