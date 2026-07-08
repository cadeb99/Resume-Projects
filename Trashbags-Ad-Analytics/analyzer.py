# analyzer.py — send aggregated data to Claude API and get structured analysis
import json
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, DEMO_MODE
from ski_calendar import get_context_string

SYSTEM_PROMPT = """You are an expert digital advertising analyst for a baggy snowpants brand.
The brand sells to three core audiences:
1. Park Riders — terrain park skiers/snowboarders, influenced by events and competitions
2. Functional Ski Market — resort and backcountry skiers at global destinations
3. Streetwear/Lifestyle — urban audiences wearing ski apparel as fashion

Your job is to produce a concise, highly actionable weekly ad performance analysis.
Always lead every section with the highest-impact finding. Cut anything not immediately actionable.
Apply hemisphere-aware seasonal context on every recommendation.
Output must be valid JSON matching the schema described in the user prompt."""

ANALYSIS_SCHEMA = """{
  "top_placements": [{"placement": str, "ctr": float, "cpc": float, "roas": float, "verdict": str}],
  "worst_placements": [{"placement": str, "ctr": float, "reason": str}],
  "top_geos": [{"geo": str, "roas": float, "hemisphere": str, "key_metric": str}],
  "top_audiences": [{"audience": str, "ctr": float, "roas": float, "best_time": str}],
  "frequency_alerts": [{"ad_id": str, "creative": str, "frequency": float, "recommendation": str}],
  "hemisphere_status": {"northern": str, "southern": str, "focus": str},
  "trending_searches": [{"term_or_city": str, "wow_change_pct": float, "action": str}],
  "snow_conditions": {"best_regions": [str], "worst_regions": [str], "opportunity_note": str},
  "upcoming_events": [{"event": str, "location": str, "date": str, "days_until": int, "tier": str, "host": str, "action": str}],
  "competitor_gaps": [{"market": str, "reason": str, "urgency": str}],
  "long_running_competitor_creatives": [{"brand": str, "longevity_days": int, "insight": str}],
  "oversaturated_markets": [{"market": str, "note": str}],
  "existing_ad_recommendations": {
    "pause": [{"target": str, "reason": str}],
    "keep_running": [{"target": str, "reason": str}],
    "shift_budget": [{"from": str, "to": str, "reason": str}],
    "geo_adjustments": [{"location": str, "action": str, "reason": str}],
    "timing_adjustments": [{"current": str, "better": str, "reason": str}],
    "audience_refinements": [{"segment": str, "action": str, "reason": str}]
  },
  "new_ad_recommendations": {
    "competitor_gaps": [{"market": str, "insight": str}],
    "park_event_opportunities": [{"event": str, "location": str, "date": str, "audience": str, "window": str}],
    "hemisphere_opportunities": [{"location": str, "season_status": str, "conditions": str}],
    "new_geo_targets": [{"city": str, "demand_signal": str, "combined_score": str}],
    "new_audience_segments": [{"segment": str, "fit": str}],
    "new_placements": [{"placement": str, "opportunity": str}]
  },
  "global_snapshot": {
    "trending_up": [str],
    "park_events_incoming": [str],
    "northern_summary": str,
    "southern_summary": str,
    "next_2_4_weeks_focus": str,
    "trending_down": [str]
  }
}"""


def analyze(dataset: dict) -> dict:
    """Send aggregated dataset to Claude and return structured analysis."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    season_context = get_context_string()
    data_summary = json.dumps(dataset, indent=2, default=str)

    user_prompt = f"""
{season_context}

AGGREGATED AD PERFORMANCE DATA:
{data_summary}

Analyze this data and return ONLY a valid JSON object matching this exact schema:
{ANALYSIS_SCHEMA}

Rules:
- Lead every array with the highest-impact item first
- All monetary values in USD
- All percentages as floats (e.g. 2.5 for 2.5%)
- Be concise — no fluff, no generic advice
- Apply hemisphere seasonality to every geo recommendation
- Factor in all 3 audience pillars for every recommendation
- Cross-reference snow conditions with ad geo targeting
- Flag any event within 21 days as urgent
- Events come in 3 tiers: "mega" (Olympics, X Games, World Cup Finals, Burton US Open — huge brand visibility),
  "major" (World Cup stops, Freeride World Tour, Red Bull events, brand-hosted comps), and "grassroots"
  (local rail jams, park openers). Mega events justify advance creative/budget planning even when
  more than 3 weeks out — call this out explicitly using each event's "host" (e.g. Red Bull, Burton,
  ESPN, FIS, The North Face) as a potential co-marketing or culturally-relevant creative angle.
- Identify retargeting opportunities for events that just ended
- Return ONLY the JSON — no markdown, no explanation
"""

    print("[analyzer] Sending data to Claude API...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        analysis = json.loads(raw)
        print("[analyzer] Analysis complete.")
        return {"status": "ok", "analysis": analysis, "model": response.model, "analyzed_at": datetime.utcnow().isoformat()}
    except json.JSONDecodeError as e:
        print(f"[analyzer] JSON parse error: {e}")
        return {"status": "error", "error": f"JSON parse failed: {e}", "raw_response": raw}
