"""
StackPulse - AI Evaluation Pipeline
Uses Claude Haiku to evaluate and score collected tools
"""

import os
import json
import time
import requests
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

EVAL_PROMPT = """You are the editorial brain of StackPulse — a newsletter that cuts through AI hype and tells builders what actually works.

Evaluate this tool/project and return a JSON object with these fields:

- signal_score: 1-10 (10 = genuinely useful, 1 = pure hype)
- audience: list of ["developers", "founders", "pms"] who benefit most
- category: one of ["llm-tool", "agent-framework", "data-tool", "devtool", "api-service", "research", "other"]
- one_liner: single punchy sentence (max 15 words) describing what it actually does
- why_it_matters: 2-3 sentences on real-world impact. No hype. Be honest.
- verdict: one of ["worth_watching", "genuinely_useful", "skip", "too_early"]
- tags: list of 3-5 relevant tags

Tool details:
Name: {name}
Description: {tagline}
Source: {source}
URL: {url}

Return ONLY valid JSON, no markdown, no explanation."""


def evaluate_tool(tool):
    if not ANTHROPIC_API_KEY:
        print("No Anthropic key found")
        return None

    prompt = EVAL_PROMPT.format(
        name=tool["name"],
        tagline=tool.get("tagline", ""),
        source=tool["source"],
        url=tool.get("url", "")
    )

    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        resp_json = res.json()
        if "content" not in resp_json:
            print(f"  API error: {resp_json.get('error', resp_json)}")
            return None
        content = resp_json["content"][0]["text"].strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        evaluation = json.loads(content)
        return evaluation
    except Exception as e:
        print(f"  Eval error for {tool['name']}: {e}")
        return None


def fetch_pending_tools():
    if not SUPABASE_URL or not SUPABASE_KEY:
        # Load from local file for testing
        import glob
        files = sorted(glob.glob("/tmp/stackpulse_collected_*.json"))
        if files:
            with open(files[-1]) as f:
                return json.load(f)
        return []

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/tools?status=eq.pending_review&limit=50",
        headers=headers,
        timeout=15
    )
    return res.json()


def save_evaluation(tool_id, evaluation):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"  [{tool_id}] score={evaluation.get('signal_score')} verdict={evaluation.get('verdict')}")
        return

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/tools?id=eq.{tool_id}",
        headers=headers,
        json={
            "signal_score": evaluation.get("signal_score"),
            "audience": evaluation.get("audience"),
            "category": evaluation.get("category"),
            "one_liner": evaluation.get("one_liner"),
            "why_it_matters": evaluation.get("why_it_matters"),
            "verdict": evaluation.get("verdict"),
            "eval_tags": evaluation.get("tags"),
            "status": "evaluated",
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        },
        timeout=15
    )


if __name__ == "__main__":
    print(f"=== StackPulse Evaluation - {datetime.now().isoformat()} ===")
    tools = fetch_pending_tools()
    print(f"Evaluating {len(tools)} tools...")

    evaluated = 0
    for tool in tools:
        print(f"  Evaluating: {tool['name']}")
        time.sleep(0.5)  # avoid rate limits
        evaluation = evaluate_tool(tool)
        if evaluation:
            save_evaluation(tool.get("id", tool["name"]), evaluation)
            evaluated += 1

    print(f"Done. Evaluated {evaluated}/{len(tools)} tools.")
