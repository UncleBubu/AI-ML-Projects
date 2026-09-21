-- ============================================================================
-- Day 10: realistic demo data, so the demo never opens on an empty database.
-- HOW: sign up in the app first, then paste this into the Supabase SQL editor,
--      change v_email below to YOUR login email, and run it. Run it ONCE.
-- Story baked in (for the insights demo): Ada Stores is your best customer but
-- has slowly gone from paying in ~2 days to ~7 days; two invoices are overdue.
-- Note: seeded "Pay link"s are placeholders. For the live payment demo, create a
-- fresh invoice in the UI (that gets a real Paystack sandbox link).
-- ============================================================================
do $$
declare
  v_email text := 'chukwuebukaofor@gmail.com';   -- <<< CHANGE THIS to your login email
  v_user  uuid;
  v_biz   uuid;
  c_ada uuid; c_bola uuid; c_chidi uuid; c_dara uuid; c_emeka uuid;
begin
  select id into v_user from auth.users where email = v_email;
  if v_user is null then raise exception 'No user with email %, sign up in the app first', v_email; end if;

  select id into v_biz from public.business where owner_id = v_user;
  if v_biz is null then
    insert into public.business(name, owner_id) values (split_part(v_email, '@', 1) || '''s business', v_user)
    returning id into v_biz;
  end if;

  if exists (select 1 from public.invoice where business_id = v_biz and payment_reference like 'SEED-%') then
    raise exception 'Demo data already loaded for this business';
  end if;

  insert into public.customer(business_id, name, email, phone) values
    (v_biz, 'Ada Stores',       'ada@example.com',   '08011111111') returning id into c_ada;
  insert into public.customer(business_id, name, email, phone) values
    (v_biz, 'Bola Logistics',   'bola@example.com',  '08022222222') returning id into c_bola;
  insert into public.customer(business_id, name, email, phone) values
    (v_biz, 'Chidi Bakery',     'chidi@example.com', '08033333333') returning id into c_chidi;
  insert into public.customer(business_id, name, email, phone) values
    (v_biz, 'Dara Fashion',     'dara@example.com',  '08044444444') returning id into c_dara;
  insert into public.customer(business_id, name, email, phone) values
    (v_biz, 'Emeka Tech Hub',   'emeka@example.com', '08055555555') returning id into c_emeka;

  -- seed_inv(customer, issued N days ago, due N days after issue, amount, paid N days after issue or null, forced status or null)
  create or replace function pg_temp.seed_inv(
    p_biz uuid, p_cust uuid, p_ago int, p_due int, p_amount numeric, p_paid_after int, p_force text default null
  ) returns void language plpgsql as $f$
  declare
    inv public.invoice; v_status public.invoice_status; v_issue timestamptz := now() - make_interval(days => p_ago);
  begin
    inv := public.create_invoice(p_biz, p_cust, v_issue + make_interval(days => p_due),
      jsonb_build_array(
        jsonb_build_object('description', 'Goods supplied',  'quantity', 1, 'unit_price', round(p_amount * 0.6, 2)),
        jsonb_build_object('description', 'Service / delivery', 'quantity', 1, 'unit_price', p_amount - round(p_amount * 0.6, 2))));

    v_status := case
      when p_force is not null then p_force::public.invoice_status
      when p_paid_after is not null then 'paid'
      when v_issue + make_interval(days => p_due) < now() then 'overdue'
      else 'sent' end;

    update public.invoice
       set issue_date = v_issue,
           status = v_status,
           payment_reference = case when p_force = 'draft' then null else 'SEED-' || inv.invoice_number end,
           checkout_url = case when p_force = 'draft' then null else 'https://checkout.paystack.com/demo-' || inv.invoice_number end
     where id = inv.id;

    if p_paid_after is not null then
      insert into public.transaction(invoice_id, amount, provider, provider_reference, paid_at)
      values (inv.id, p_amount, 'seed', 'SEED-' || inv.invoice_number, v_issue + make_interval(days => p_paid_after));
      update public.invoice set amount_paid = p_amount where id = inv.id;
    end if;
  end $f$;

  -- Ada: best customer, getting slower (2d -> 2d -> 3d -> 6d -> 7d)
  perform pg_temp.seed_inv(v_biz, c_ada, 35, 14, 150000, 2);
  perform pg_temp.seed_inv(v_biz, c_ada, 28, 14, 120000, 2);
  perform pg_temp.seed_inv(v_biz, c_ada, 21, 14, 180000, 3);
  perform pg_temp.seed_inv(v_biz, c_ada, 14, 14, 200000, 6);
  perform pg_temp.seed_inv(v_biz, c_ada,  8, 14, 220000, 7);
  -- Bola: steady, slowish
  perform pg_temp.seed_inv(v_biz, c_bola, 30, 14,  80000, 10);
  perform pg_temp.seed_inv(v_biz, c_bola, 16, 14,  95000, 12);
  perform pg_temp.seed_inv(v_biz, c_bola,  5, 14,  60000, null);          -- sent, not yet due
  -- Chidi: two overdue
  perform pg_temp.seed_inv(v_biz, c_chidi, 20,  7,  45000, null);         -- overdue
  perform pg_temp.seed_inv(v_biz, c_chidi, 12,  5,  30000, null);         -- overdue
  -- Dara: prompt
  perform pg_temp.seed_inv(v_biz, c_dara, 10, 14,  70000, 1);
  perform pg_temp.seed_inv(v_biz, c_dara,  3, 14,  85000, null);          -- sent
  -- Emeka: one big overdue, one recent paid, plus a draft and a void
  perform pg_temp.seed_inv(v_biz, c_emeka, 25, 15, 300000, null);         -- overdue (large)
  perform pg_temp.seed_inv(v_biz, c_emeka,  6, 14, 120000, 5);
  perform pg_temp.seed_inv(v_biz, c_emeka,  2, 14,  50000, null, 'draft');
  perform pg_temp.seed_inv(v_biz, c_emeka, 18, 14,  40000, null, 'void');

  -- ~5 weeks of expenses (dates at noon to sit safely inside their day)
  insert into public.expense(business_id, category, amount, expense_date, note) values
    (v_biz, 'rent',      150000, date_trunc('month', now()) + interval '11 hours', 'Shop rent'),
    (v_biz, 'salaries',  180000, date_trunc('month', now()) + interval '2 days 11 hours', 'Staff salaries'),
    (v_biz, 'utilities',  22000, now() - interval '20 days', 'Electricity'),
    (v_biz, 'utilities',  18500, now() - interval '5 days',  'Internet + power'),
    (v_biz, 'supplies',   35000, now() - interval '27 days', 'Stock top-up'),
    (v_biz, 'supplies',   41000, now() - interval '13 days', 'Packaging'),
    (v_biz, 'supplies',   28000, now() - interval '4 days',  'Printer ink and paper'),
    (v_biz, 'transport',   6500, now() - interval '30 days', 'Delivery'),
    (v_biz, 'transport',   7200, now() - interval '22 days', 'Delivery'),
    (v_biz, 'transport',   5800, now() - interval '15 days', 'Delivery'),
    (v_biz, 'transport',   9000, now() - interval '8 days',  'Delivery'),
    (v_biz, 'transport',   6000, now() - interval '2 days',  'Delivery'),
    (v_biz, 'other',      12000, now() - interval '9 days',  'Accountant fee');

  raise notice 'Demo data loaded for %', v_email;
end $$;
