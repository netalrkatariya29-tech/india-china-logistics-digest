"""Reads: a list of article dicts (from fetch_news). Writes: returns the same list with an
"inference" field added to each, plus an optional weekly big-picture summary string.

Makes ONE batched call to Gemini's free tier for all of today's articles (JSON mode),
so the daily quota usage stays tiny regardless of how many articles were fetched.
"""
import json
import os

from google import genai
from google.genai import types

# Override with the GEMINI_MODEL env var if Google renames/retires this model later.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

FALLBACK_INFERENCE = "(inference unavailable today)"

DAILY_PROMPT = """You are a logistics and trade analyst writing for someone who follows the \
India and China logistics/import-export sector but has very little time to read.

For EACH article below, write ONE short sentence (max ~20 words) answering: \
"what does this actually mean for the India/China logistics or trade sector?" \
Be concrete and specific, not generic. Do not just restate the headline.

Return ONLY a JSON array, same order as the input, one object per article:
[{{"id": "<the article id, copied exactly>", "inference": "<your one-sentence takeaway>"}}, ...]

Articles:
{articles_json}
"""

WEEKLY_PROMPT = """You are a logistics and trade analyst. Below are this week's India/China \
logistics and trade news headlines with their daily inferences. Connect the dots: write ONE \
short paragraph (3-4 sentences max) describing the single biggest pattern or theme across the \
week, and what it suggests is coming next.

Return ONLY a JSON object: {{"weekly_summary": "<your paragraph>"}}

This week's items:
{items_json}
"""


def _client():
    api_key = os.environ["GEMINI_API_KEY"]
    return genai.Client(api_key=api_key)


def _call_json(client, prompt):
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def add_inferences(articles):
    """Adds an 'inference' field to each article dict, in place-safe (returns a new list)."""
    if not articles:
        return articles

    client = _client()
    slim = [{"id": a["id"], "title": a["title"], "snippet": a["snippet"], "category": a["category"]} for a in articles]
    prompt = DAILY_PROMPT.format(articles_json=json.dumps(slim, ensure_ascii=False))

    inference_by_id = {}
    try:
        results = _call_json(client, prompt)
        for item in results:
            inference_by_id[item.get("id")] = item.get("inference", FALLBACK_INFERENCE)
    except Exception as exc:
        print(f"  [warn] Gemini batch call failed, using fallback for all items: {exc}")

    for article in articles:
        article["inference"] = inference_by_id.get(article["id"], FALLBACK_INFERENCE)

    return articles


def weekly_summary(week_articles):
    """Returns a short weekly big-picture paragraph, or None if it can't be generated."""
    if not week_articles:
        return None

    client = _client()
    slim = [{"title": a["title"], "inference": a.get("inference", "")} for a in week_articles]
    prompt = WEEKLY_PROMPT.format(items_json=json.dumps(slim, ensure_ascii=False))

    try:
        result = _call_json(client, prompt)
        return result.get("weekly_summary")
    except Exception as exc:
        print(f"  [warn] Gemini weekly summary failed: {exc}")
        return None
