-- Run this in Supabase SQL Editor

create table if not exists orders (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  name text not null,
  insta text default '',
  address text not null,
  phone text default '',
  pincode text default '',
  product text default '',
  amount numeric default 0,
  weight numeric default 500,
  payment text default 'prepaid',
  notes text default '',
  status text default 'pending' check (status in ('pending','shipped','delivered','cancelled')),
  awb text default '',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Row Level Security (RLS)
alter table orders enable row level security;

-- Policy: users can only see their own orders
create policy "Users can manage own orders"
  on orders for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Auto-update updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger orders_updated_at
  before update on orders
  for each row execute function update_updated_at();
