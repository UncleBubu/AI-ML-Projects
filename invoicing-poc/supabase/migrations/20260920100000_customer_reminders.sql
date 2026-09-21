-- ============================================================================
-- Customer payment reminders: audit log
-- ============================================================================
-- Every attempt to contact a customer (email/SMS) is recorded here. It gives us:
--   * a cooldown (don't nag the same customer about the same invoice twice a day)
--   * an audit trail (who was contacted, when, did it work)
--   * "last reminded" in the UI
-- Append-only, like every other financial/audit record in this project.
create table public.reminder_log (
  id          uuid primary key default gen_random_uuid(),
  invoice_id  uuid not null references public.invoice(id),
  business_id uuid not null references public.business(id) on delete cascade,
  channel     text not null check (channel in ('email', 'sms')),
  recipient   text not null,
  status      text not null check (status in ('sent', 'failed')),
  error       text,
  sent_at     timestamptz not null default now()
);

create index reminder_log_invoice_idx on public.reminder_log(invoice_id, sent_at desc);

create trigger reminder_log_append_only
  before update or delete on public.reminder_log
  for each row execute function public.forbid_mutation();

alter table public.reminder_log enable row level security;

create policy "Owners can view their reminder log"
  on public.reminder_log for select
  using (business_id in (select id from public.business where owner_id = auth.uid()));
-- No insert/update/delete policies: only the trusted backend (service role) writes here.
