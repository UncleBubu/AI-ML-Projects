-- ============================================================================
-- Day 9: prove RLS isolates businesses.
-- Run in the Supabase SQL editor (or psql). Everything is rolled back at the end,
-- so it leaves no data behind. Expected: every "PASS" line, and no exceptions.
-- ============================================================================
begin;

do $$
declare
  ua uuid := gen_random_uuid();  ub uuid := gen_random_uuid();
  ba uuid := gen_random_uuid();  bb uuid := gen_random_uuid();
  ca uuid := gen_random_uuid();  cb uuid := gen_random_uuid();
  ia uuid;  n int;
begin
  -- Two users, two businesses, one customer + invoice + expense each (as superuser).
  insert into auth.users(id, email) values (ua, ua || '@test.local'), (ub, ub || '@test.local');
  insert into public.business(id, name, owner_id) values (ba, 'A biz', ua), (bb, 'B biz', ub);
  insert into public.customer(id, business_id, name, email) values (ca, ba, 'A cust', 'a@x.com'), (cb, bb, 'B cust', 'b@x.com');
  ia := (public.create_invoice(ba, ca, now() + interval '3 days', '[{"description":"x","quantity":1,"unit_price":100}]')).id;
  perform public.create_invoice(bb, cb, now() + interval '3 days', '[{"description":"y","quantity":1,"unit_price":200}]');
  insert into public.expense(business_id, category, amount) values (ba, 'rent', 10), (bb, 'rent', 20);

  -- Act as user A, exactly like the browser with the anon key + A's login token.
  perform set_config('request.jwt.claim.sub', ua::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', ua, 'role', 'authenticated')::text, true);
  set local role authenticated;

  select count(*) into n from public.business;          assert n = 1, 'A sees only its own business';
  select count(*) into n from public.customer;          assert n = 1, 'A sees only its own customers';
  select count(*) into n from public.invoice;           assert n = 1, 'A sees only its own invoices';
  select count(*) into n from public.invoice_line_item; assert n = 1, 'A sees only its own line items';
  select count(*) into n from public.expense;           assert n = 1, 'A sees only its own expenses';
  select count(*) into n from public.profiles;          assert n = 1, 'A sees only its own profile';
  raise notice 'PASS: user A can read only A''s data';

  select count(*) into n from public.invoice where business_id = bb;
  assert n = 0, 'A cannot read B invoices even when asking by id';
  raise notice 'PASS: cross-tenant read by business_id returns nothing';

  -- Writes from the browser role must all fail.
  begin
    insert into public.invoice(business_id, customer_id, invoice_number, due_date, total_amount)
      values (ba, ca, 'HACK-1', now(), 1);
    raise exception 'FAIL: direct invoice insert was allowed';
  exception when insufficient_privilege then raise notice 'PASS: direct invoice insert blocked'; end;

  begin
    update public.invoice set total_amount = 1 where id = ia;
    raise exception 'FAIL: direct invoice update was allowed';
  exception when insufficient_privilege then raise notice 'PASS: direct invoice update blocked'; end;

  begin
    perform public.record_payment('anything', 1);
    raise exception 'FAIL: record_payment callable by a user';
  exception when insufficient_privilege then raise notice 'PASS: record_payment not callable by users'; end;

  begin
    perform public.report_summary(bb, now() - interval '1 day', now());
    raise exception 'FAIL: report_summary callable by a user';
  exception when insufficient_privilege then raise notice 'PASS: report_summary not callable by users'; end;
end $$;

rollback;
