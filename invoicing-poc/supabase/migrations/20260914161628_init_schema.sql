-- Enable UUID generation
-- postgres does not generate uuid by default, this code turns it on without creating an error if it already is.
create extension if not exists "pgcrypto";

-- Enum types
create type invoice_status as enum ('draft', 'sent', 'paid', 'overdue', 'void');
create type expense_category as enum ('rent', 'transport', 'supplies', 'utilities', 'salaries', 'other');

-- Business table
create table public.business (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz default now()
);

-- Customer table
create table public.customer (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references public.business(id) on delete cascade,
  name text not null,
  phone text,
  email text,
  created_at timestamptz default now()
);


-- Invoice table
create table public.invoice (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references public.business(id) on delete cascade,
  customer_id uuid not null references public.customer(id),
  invoice_number text not null,
  issue_date timestamptz default now(),
  due_date timestamptz not null,
  status invoice_status not null default 'draft',
  total_amount numeric(12,2) not null default 0,
  amount_paid numeric(12,2) not null default 0,
  payment_reference text,
  reminder_sent_at timestamptz
);

-- Invoice line items
create table public.invoice_line_item (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoice(id) on delete cascade,
  description text not null,
  quantity integer not null,
  unit_price numeric(12,2) not null,
  line_total numeric(12,2) not null
);

-- Transactions (append-only — never updated after insert)
create table public.transaction (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoice(id),
  amount numeric(12,2) not null,
  provider text not null,
  provider_reference text not null unique,
  paid_at timestamptz default now()
);

-- Expenses
create table public.expense (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references public.business(id) on delete cascade,
  category expense_category not null,
  amount numeric(12,2) not null,
  expense_date timestamptz default now(),
  note text
);
--Supabase manages its own internal `auth.users` table — you can't add custom columns to it directly. 
--The standard pattern is a separate `public.profiles` table that gets automatically populated every time someone signs up, via a **trigger** (a function that runs automatically on a database event).

-- Profiles table, mirrors auth.users
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  created_at timestamptz default now()
);

-- Function that runs on every new signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql security definer;

-- The trigger itself: fires after every insert into auth.users
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

--Row Level Security (RLS) Policies
-- Turn on RLS for every table
alter table public.business enable row level security;
alter table public.customer enable row level security;
alter table public.invoice enable row level security;
alter table public.invoice_line_item enable row level security;
alter table public.transaction enable row level security;
alter table public.expense enable row level security;

-- BUSINESS: direct ownership check
create policy "Owners can view their business"
  on public.business for select
  using (owner_id = auth.uid());

create policy "Owners can insert their business"
  on public.business for insert
  with check (owner_id = auth.uid());

-- CUSTOMER: ownership via business
create policy "Owners can view their customers"
  on public.customer for select
  using (business_id in (select id from public.business where owner_id = auth.uid()));

create policy "Owners can insert their customers"
  on public.customer for insert
  with check (business_id in (select id from public.business where owner_id = auth.uid()));

-- INVOICE: ownership via business
create policy "Owners can view their invoices"
  on public.invoice for select
  using (business_id in (select id from public.business where owner_id = auth.uid()));

create policy "Owners can insert their invoices"
  on public.invoice for insert
  with check (business_id in (select id from public.business where owner_id = auth.uid()));

-- INVOICE_LINE_ITEM: ownership via invoice via business
create policy "Owners can view their invoice line items"
  on public.invoice_line_item for select
  using (
    invoice_id in (
      select id from public.invoice where business_id in (
        select id from public.business where owner_id = auth.uid()
      )
    )
  );

create policy "Owners can insert their invoice line items"
  on public.invoice_line_item for insert
  with check (
    invoice_id in (
      select id from public.invoice where business_id in (
        select id from public.business where owner_id = auth.uid()
      )
    )
  );
-- TRANSACTION: ownership via invoice via business (read-only from the app's perspective)
create policy "Owners can view their transactions"
  on public.transaction for select
  using (
    invoice_id in (
      select id from public.invoice where business_id in (
        select id from public.business where owner_id = auth.uid()
      )
    )
  );

-- EXPENSE: ownership via business
create policy "Owners can view their expenses"
  on public.expense for select
  using (business_id in (select id from public.business where owner_id = auth.uid()));

create policy "Owners can insert their expenses"
  on public.expense for insert
  with check (business_id in (select id from public.business where owner_id = auth.uid()));