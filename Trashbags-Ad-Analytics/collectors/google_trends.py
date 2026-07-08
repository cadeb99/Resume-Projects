# collectors/google_trends.py — live Google Trends via pytrends
from datetime import datetime
from pytrends.request import TrendReq
from ski_calendar import NORTHERN_HEMISPHERE_TARGETS, SOUTHERN_HEMISPHERE_TARGETS

SEARCH_TERMS = ["snowpants", "ski pants baggy", "park skiing", "slopestyle", "halfpipe competition"]


def get_data() -> dict:
    """Pull week-over-week Google Trends data for ski/park terms by region."""
    try:
        pytrends = TrendReq(hl="en-US", tz=0)
        city_trends = []
        term_trends = []

        for term in SEARCH_TERMS[:3]:
            pytrends.build_payload([term], timeframe="now 7-d", geo="")
            interest = pytrends.interest_over_time()
            if interest.empty:
                continue
            recent = interest[term].tail(7).mean()
            prior = interest[term].head(7).mean()
            wow = round(((recent - prior) / max(prior, 1)) * 100, 1)
            term_trends.append({
                "term": term,
                "interest": int(recent),
                "wow_change_pct": wow,
                "is_spiking": wow >= 25,
                "category": "park" if "park" in term or "slopestyle" in term or "halfpipe" in term else "general",
            })

        spiking_cities = [c for c in city_trends if c.get("is_spiking")]
        spiking_terms = [t for t in term_trends if t["is_spiking"]]

        return {
            "source": "google_trends",
            "status": "ok",
            "retrieved_at": datetime.utcnow().isoformat(),
            "city_trends": city_trends,
            "term_trends": term_trends,
            "spiking_cities": spiking_cities,
            "spiking_terms": spiking_terms,
        }

    except Exception as e:
        return {"source": "google_trends", "status": "error", "error": str(e), "city_trends": [], "term_trends": []}
