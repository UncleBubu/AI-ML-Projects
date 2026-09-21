-- ============================================================================
-- Day 3: idempotent, atomic payment recording
-- ============================================================================
-- Called by BOTH the Paystack webhook and the manual "verify" fallback.
-- Because both paths go through this one function, "how a payment is recorded"
-- exists in exactly one place.
--
-- Concurrency/idempotency:
--   * `for update` locks the invoice row, so two simultaneous deliveries of the
--     same webhook run one after the other, not at the same time.
--   * `on conflict (provider_reference) do nothing` (backed by the UNIQUE
--     constraint from Day 1) makes the second delivery a harmless no-op.
create or replace function public.record_payment(
  p_reference text,
  p_amount    numeric,
  p_provider  text default 'paystack'
)
returns jsonb
language plpgsql
as $$
declare
  v_invoice public.invoice%rowtype;
  v_tx_id   uuid;
  v_paid    numeric(12,2);
  v_status  public.invoice_status;
begin
  select * into v_invoice
    from public.invoice
   where payment_reference = p_reference
   for update;

  if not found then
    return jsonb_build_object('result', 'invoice_not_found');
  end if;

  insert into public.transaction (invoice_id, amount, provider, provider_reference)
  values (v_invoice.id, p_amount, p_provider, p_reference)
  on conflict (provider_reference) do nothing
  returning id into v_tx_id;

  if v_tx_id is null then
    return jsonb_build_object('result', 'duplicate', 'invoice_id', v_invoice.id);
  end if;

  v_paid := v_invoice.amount_paid + p_amount;

  -- Only unpaid states can become 'paid'. A voided invoice that somehow got paid
  -- keeps status 'void' (money is still recorded in `transaction` for a human
  -- to refund) rather than being silently resurrected.
  v_status := case
    when v_invoice.status in ('draft', 'sent', 'overdue') and v_paid >= v_invoice.total_amount
      then 'paid'::public.invoice_status
    else v_invoice.status
  end;

  update public.invoice
     set amount_paid = v_paid,
         status      = v_status
   where id = v_invoice.id;

  return jsonb_build_object(
    'result',      'recorded',
    'invoice_id',  v_invoice.id,
    'amount_paid', v_paid,
    'status',      v_status
  );
end;
$$;

revoke all on function public.record_payment(text, numeric, text) from public, anon, authenticated;
grant execute on function public.record_payment(text, numeric, text) to service_role;
