-- Removes the data created by seed_demo.sql (identified by the demo customers' example.com emails
-- and the seeded expense notes). Run in the Supabase SQL editor. Real data is untouched.
-- The append-only triggers are lifted only for the duration of this script, then restored.
begin;
alter table public.transaction  disable trigger transaction_append_only;
alter table public.reminder_log disable trigger reminder_log_append_only;

with demo_customers as (
  select id from public.customer
   where email in ('ada@example.com','bola@example.com','chidi@example.com','dara@example.com','emeka@example.com')
), demo_invoices as (
  select id from public.invoice where customer_id in (select id from demo_customers)
)
, d1 as (delete from public.transaction       where invoice_id in (select id from demo_invoices))
, d2 as (delete from public.reminder_log      where invoice_id in (select id from demo_invoices))
, d3 as (delete from public.invoice_line_item where invoice_id in (select id from demo_invoices))
, d4 as (delete from public.invoice           where id in (select id from demo_invoices))
delete from public.customer where id in (select id from demo_customers);

delete from public.expense where note in ('Shop rent','Staff salaries','Electricity','Internet + power','Stock top-up',
  'Packaging','Printer ink and paper','Delivery','Accountant fee');

alter table public.transaction  enable trigger transaction_append_only;
alter table public.reminder_log enable trigger reminder_log_append_only;
commit;
