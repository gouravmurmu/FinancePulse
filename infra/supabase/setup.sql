-- One-time Supabase setup, run as `postgres` in the SQL editor (or via the
-- Supabase MCP). Creates the login the API uses and the privileges its
-- migrations need. Replace <password> with a generated secret; store it only
-- in the Render DATABASE_URL.

-- 1. API login role. It owns the app tables and runs migrations on boot.
create role marketpulse_api with login password '<password>' noinherit;
grant usage, create on schema public to marketpulse_api;
-- Lets postgres alter tables owned by the API role (step 3 below).
grant marketpulse_api to postgres;
-- auth.uid() in RLS policies needs USAGE on schema auth, which postgres
-- cannot grant directly; membership in `authenticated` provides it.
grant authenticated to marketpulse_api with inherit true;

-- 2. Connection string for Render (session pooler, IPv4):
--    postgresql://marketpulse_api.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require

-- 3. After the first deploy has applied migration 0001, add the foreign key
--    the app role is not allowed to create (postgres holds REFERENCES on auth.users).
alter table public.profiles
  add constraint fk_profiles_id_users
  foreign key (id) references auth.users (id) on delete cascade;
