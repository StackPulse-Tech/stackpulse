# StackPulse — Setup & Operations Guide

## What It Is
Curated AI tool intelligence for developers, founders, and PMs.
Weekly newsletter + searchable database. Signal over noise.

## Architecture
```
Sources (ProductHunt, HN, GitHub)
    → collect.py (daily via GitHub Actions)
    → evaluate.py (Claude Haiku, ~$0.001/tool)
    → Supabase DB
    → digest.py (weekly, Monday 8AM UTC)
    → Beehiiv draft (review + send)
```

## One-Time Setup

### 1. Supabase
- Go to Supabase dashboard → SQL Editor
- Run `supabase/schema.sql`
- Get: Settings → API → `URL` and `anon key`

### 2. Beehiiv
- Go to Settings → API → generate API key
- Get Publication ID from URL: `app.beehiiv.com/publications/pub_XXXXX`

### 3. GitHub Secrets
In the GitHub repo settings → Secrets → add:
```
ANTHROPIC_API_KEY   → your Anthropic key
SUPABASE_URL        → https://xxxx.supabase.co
SUPABASE_KEY        → your anon key
BEEHIIV_API_KEY     → your Beehiiv API key
BEEHIIV_PUB_ID      → pub_XXXXXXXXXXXXX
```

### 4. Push to GitHub
```bash
git init
git add .
git commit -m "Initial StackPulse pipeline"
git remote add origin https://github.com/getstackpulse/stackpulse
git push -u origin main
```

## Running Manually
```bash
# Install deps
pip install requests beautifulsoup4

# Test collection (no Supabase needed, saves to /tmp)
python pipeline/collect.py

# Test evaluation
ANTHROPIC_API_KEY=xxx python pipeline/evaluate.py

# Generate digest draft
python pipeline/digest.py
```

## Credentials
See `stackpulse-credentials.md` on the VPS (private, not in git).

## Schedule
- Daily 6AM UTC: collect + evaluate
- Monday 8AM UTC: generate digest draft in Beehiiv
- Review draft → hit send
