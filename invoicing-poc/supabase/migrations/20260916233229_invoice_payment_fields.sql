-- Where we store Paystack's hosted checkout URL
alter table public.invoice
  add column if not exists checkout_url text;

-- A running counter per business, used to generate invoice numbers
alter table public.business
  add column if not exists invoice_seq integer not null default 0;

-- Atomically increments and returns the next invoice number for a business.
-- Doing the increment AND the read in one SQL statement (not two JS round trips)
-- is what prevents two concurrent "create invoice" requests from both
-- getting the same invoice number.
create or replace function public.next_invoice_seq(p_business_id uuid)
returns integer
language sql
as $$
  update public.business
  set invoice_seq = invoice_seq + 1
  where id = p_business_id
  returning invoice_seq;
$$;
