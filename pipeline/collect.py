"""
StackPulse - Content Collection Pipeline
Collects new AI tools from ProductHunt, HackerNews, GitHub Trending
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

HEADERS = {"User-Agent": "StackPulse/1.0 (getstackpulse.tech)"}


# ─── ProductHunt ────────────────────────────────────────────────────────────

def fetch_producthunt():
    """Fetch top posts from ProductHunt via their GraphQL API (no key needed for basic)"""
    query = """
    {
      posts(order: VOTES, topic: "artificial-intelligence") {
        edges {
          node {
            id name tagline url
            votesCount
            createdAt
            topics { edges { node { name } } }
          }
        }
      }
    }
    """
    try:
        res = requests.post(
            "https://api.producthunt.com/v2/api/graphql",
            json={"query": query},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=15
        )
        data = res.json()
        posts = data.get("data", {}).get("posts", {}).get("edges", [])
        tools = []
        for edge in posts[:20]:
            node = edge["node"]
            tools.append({
                "source": "producthunt",
                "name": node["name"],
                "tagline": node["tagline"],
                "url": node["url"],
                "votes": node.get("votesCount", 0),
                "tags": [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })
        print(f"ProductHunt: {len(tools)} tools")
        return tools
    except Exception as e:
        print(f"ProductHunt error: {e}")
        return []


# ─── Hacker News ────────────────────────────────────────────────────────────

def fetch_hackernews():
    """Fetch Show HN posts related to AI tools"""
    try:
        # Get recent Show HN stories
        res = requests.get(
            "https://hacker-news.firebaseio.com/v0/showstories.json",
            timeout=15
        )
        story_ids = res.json()[:50]

        tools = []
        for sid in story_ids:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=10
                ).json()
                title = item.get("title", "").lower()
                # Filter for AI/ML related
                if any(kw in title for kw in ["ai", "llm", "gpt", "ml", "agent", "neural", "model"]):
                    tools.append({
                        "source": "hackernews",
                        "name": item.get("title", ""),
                        "tagline": f"HN Score: {item.get('score', 0)} | {item.get('descendants', 0)} comments",
                        "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                        "votes": item.get("score", 0),
                        "tags": ["hackernews", "show-hn"],
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    })
                time.sleep(0.05)  # be polite
            except:
                pass

        print(f"HackerNews: {len(tools)} tools")
        return tools
    except Exception as e:
        print(f"HackerNews error: {e}")
        return []


# ─── GitHub Trending ────────────────────────────────────────────────────────

def fetch_github_trending():
    """Scrape GitHub trending for AI/ML repos"""
    try:
        from bs4 import BeautifulSoup
        res = requests.get(
            "https://github.com/trending/python?since=daily&spoken_language_code=en",
            headers=HEADERS,
            timeout=15
        )
        soup = BeautifulSoup(res.text, "html.parser")
        repos = soup.select("article.Box-row")

        tools = []
        for repo in repos[:20]:
            name_tag = repo.select_one("h2 a")
            desc_tag = repo.select_one("p")
            stars_tag = repo.select_one("a[href*='/stargazers']")

            if not name_tag:
                continue

            name = name_tag.get_text(strip=True).replace("\n", "").replace(" ", "")
            desc = desc_tag.get_text(strip=True) if desc_tag else ""
            stars_text = stars_tag.get_text(strip=True).replace(",", "") if stars_tag else "0"

            # Filter AI/ML repos
            if any(kw in desc.lower() for kw in ["ai", "llm", "model", "agent", "gpt", "neural", "ml", "vision"]):
                tools.append({
                    "source": "github_trending",
                    "name": name,
                    "tagline": desc,
                    "url": f"https://github.com/{name}",
                    "votes": int(stars_text) if stars_text.isdigit() else 0,
                    "tags": ["github", "trending", "open-source"],
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })

        print(f"GitHub Trending: {len(tools)} tools")
        return tools
    except Exception as e:
        print(f"GitHub Trending error: {e}")
        return []


# ─── Dedup & Save ───────────────────────────────────────────────────────────

def get_tool_id(tool):
    """Stable ID based on name + source"""
    raw = f"{tool['source']}:{tool['name'].lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def save_to_supabase(tools):
    if not SUPABASE_URL or not SUPABASE_KEY:
        # Save locally if no Supabase config yet
        out = f"/tmp/stackpulse_collected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out, "w") as f:
            json.dump(tools, f, indent=2)
        print(f"Saved {len(tools)} tools locally to {out}")
        return

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates"
    }

    records = []
    for t in tools:
        records.append({
            "id": get_tool_id(t),
            "source": t["source"],
            "name": t["name"],
            "tagline": t["tagline"],
            "url": t["url"],
            "votes": t.get("votes", 0),
            "tags": t.get("tags", []),
            "collected_at": t["collected_at"],
            "status": "pending_review"
        })

    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/tools",
        headers=headers,
        json=records,
        timeout=30
    )
    print(f"Supabase: {res.status_code} - saved {len(records)} tools")


if __name__ == "__main__":
    print(f"=== StackPulse Collection - {datetime.now().isoformat()} ===")
    tools = []
    tools.extend(fetch_producthunt())
    tools.extend(fetch_hackernews())
    tools.extend(fetch_github_trending())
    print(f"Total collected: {len(tools)}")
    save_to_supabase(tools)
