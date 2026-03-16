-- StackPulse Database Schema
-- Run this in Supabase SQL editor

create table if not exists tools (
  id              text primary key,
  source          text not null,
  name            text not null,
  tagline         text,
  url             text,
  votes           integer default 0,
  tags            text[],
  collected_at    timestamptz default now(),

  -- Evaluation fields
  signal_score    integer,
  audience        text[],
  category        text,
  one_liner       text,
  why_it_matters  text,
  verdict         text,
  eval_tags       text[],
  status          text default 'pending_review',
  evaluated_at    timestamptz,

  created_at      timestamptz default now()
);

-- Index for fast filtering
create index if not exists tools_status_idx on tools(status);
create index if not exists tools_verdict_idx on tools(verdict);
create index if not exists tools_signal_idx on tools(signal_score desc);
create index if not exists tools_source_idx on tools(source);

-- View for newsletter-ready tools
create or replace view digest_ready as
  select * from tools
  where status = 'evaluated'
    and verdict != 'skip'
    and signal_score >= 6
  order by signal_score desc, collected_at desc;
