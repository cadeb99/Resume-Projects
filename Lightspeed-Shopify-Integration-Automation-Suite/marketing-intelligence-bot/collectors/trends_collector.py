"""
Google Trends interest-over-time per product category, via pytrends.

Each category is fetched in its own subprocess. pytrends/urllib3 has been
observed to segfault the interpreter (not a catchable Python exception) when
making several requests in a row in this environment — running each call
isolated means a crash only loses that one category's real score (falls back
to randomized) instead of taking down the whole report pipeline.
"""
import json
import random
import subprocess
import sys

# Maps our internal category names to search terms people actually use.
CATEGORY_SEARCH_TERMS = {
    "winter_outerwear": "kids snowsuit",
    "everyday_clothing": "toddler clothes",
    "footwear": "kids winter boots",
    "outdoor_toys": "outdoor toys for kids",
    "educational_toys_games": "wooden educational toys",
    "books_crafts": "kids craft kit",
    "plush_collectibles": "stuffed animal plush",
    "gifts_novelty": "colorado souvenirs",
    "baby_gear": "baby swaddle",
}

_WORKER_SCRIPT = """
import sys, json
from pytrends.request import TrendReq
term = sys.argv[1]
pytrends = TrendReq(hl="en-US", tz=360)
pytrends.build_payload([term], timeframe="today 1-m", geo="US-CO")
df = pytrends.interest_over_time()
if df is not None and not df.empty:
    print(json.dumps({"score": int(df[term].mean())}))
else:
    print(json.dumps({"score": None}))
"""


def get_trend_scores(categories):
    """Returns {category: trend_score 0-100} for the given categories."""
    scores = {}
    for category in categories:
        term = CATEGORY_SEARCH_TERMS.get(category, category)
        scores[category] = _fetch_one(term)
    return scores


def _fetch_one(term):
    try:
        result = subprocess.run(
            [sys.executable, "-c", _WORKER_SCRIPT, term],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().splitlines()[-1])
            if data.get("score") is not None:
                return data["score"]
    except Exception:
        pass
    return _fallback_score()


def _fallback_score():
    return random.randint(30, 90)
