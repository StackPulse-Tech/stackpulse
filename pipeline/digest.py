"""
StackPulse - Weekly Digest Generator
Pulls top evaluated tools and generates the newsletter draft
"""

import os
import json
import requests
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BEEHIIV_API_KEY = os.environ.get("BEEHIIV_API_KEY")
BEEHIIV_PUB_ID = os.environ.get("BEEHIIV_PUB_ID")

DIGEST_PROMPT = """You are the editor of StackPulse — a no-BS newsletter for developers, founders, and PMs who want to know what's actually worth their attention in AI.

Write this week's digest in the StackPulse voice:
- Sharp, direct, zero fluff
- Technical credibility without being gatekeepy  
- One punchy insight per tool
- Honest verdicts — if it's overhyped, say so

Format (use HTML for Beehiiv):
1. Opening hook (2 sentences max — what's the big theme this week?)
2. Top 5 tools (each: name, one_liner, why_it_matters, verdict badge)
3. Quick Hits (3-5 tools worth a glance, one line each)
4. Closing thought (1 sentence — what to watch next week)

Tools to cover:
{tools_json}

Return clean HTML ready for a newsletter. No markdown."""


def fetch_top_tools(limit=10):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/tools?status=eq.evaluated&verdict=neq.skip&order=signal_score.desc&limit={limit}",
        headers=headers,
        timeout=15
    )
    return res.json()


def generate_digest(tools):
    tools_summary = [
        {
            "name": t["name"],
            "one_liner": t.get("one_liner", t.get("tagline", "")),
            "why_it_matters": t.get("why_it_matters", ""),
            "verdict": t.get("verdict", ""),
            "signal_score": t.get("signal_score", 0),
            "url": t.get("url", ""),
            "source": t.get("source", ""),
        }
        for t in tools
    ]

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-haiku-4-5",
            "max_tokens": 2048,
            "messages": [{
                "role": "user",
                "content": DIGEST_PROMPT.format(tools_json=json.dumps(tools_summary, indent=2))
            }]
        },
        timeout=60
    )
    return res.json()["content"][0]["text"]


def save_digest_to_repo(subject, html_content, date_str):
    """Save digest as HTML file in the repo for manual review."""
    out_dir = "digests"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{date_str}.html"
    with open(out_path, "w") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body>
<h1>{subject}</h1>
<p><em>Generated: {datetime.now().isoformat()} — Review and paste into Beehiiv dashboard</em></p>
<hr>
{html_content}
</body>
</html>""")
    print(f"Digest saved to repo: {out_path}")
    return out_path


def create_beehiiv_draft(subject, html_content, date_str):
    if not BEEHIIV_API_KEY:
        # Manual mode — save to repo file for review
        return save_digest_to_repo(subject, html_content, date_str)

    week = datetime.now().strftime("%b %d, %Y")
    res = requests.post(
        f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/posts",
        headers={
            "Authorization": f"Bearer {BEEHIIV_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "subject": subject,
            "content": {"free": {"web": html_content, "email": html_content}},
            "status": "draft",
            "meta_default_description": f"StackPulse weekly digest — {week}",
        },
        timeout=30
    )
    print(f"Beehiiv draft created: {res.status_code}")
    return res.json()


if __name__ == "__main__":
    print(f"=== StackPulse Digest - {datetime.now().isoformat()} ===")
    tools = fetch_top_tools(limit=10)
    print(f"Found {len(tools)} evaluated tools")

    if not tools:
        print("No tools to digest yet.")
        exit(0)

    print("Generating digest...")
    html = generate_digest(tools)

    date_str = datetime.now().strftime("%Y-%m-%d")
    week = datetime.now().strftime("%b %d")
    subject = f"StackPulse #{week} — What Actually Works This Week"
    create_beehiiv_draft(subject, html, date_str)
    print("Done.")
