# dummy/dummy_meta_ads.py — realistic fake Meta ad performance data
import random
from datetime import datetime, timedelta


PLACEMENTS = ["Feed", "Reels", "Stories", "Explore"]
GEOS = [
    "Denver CO", "Salt Lake City UT", "Whistler BC", "Queenstown NZ",
    "Perisher NSW", "Innsbruck Austria", "Sapporo Japan", "Park City UT",
    "Jackson Hole WY", "Mammoth CA", "Bariloche Argentina", "Laax Switzerland",
]
AUDIENCES = [
    "18-24 Park Riders", "25-34 Park Riders",
    "18-24 Streetwear", "25-34 Streetwear",
    "Ski Enthusiasts 25-44", "Outdoor Lifestyle 18-35",
    "Lookalike — Past Purchasers", "Retargeting — Site Visitors",
]
CREATIVE_NAMES = [
    "Park Riding Edit — Slow Mo Rails", "Baggy Pants Product Flat Lay",
    "UGC — Rider Review Compilation", "Lifestyle — City Street Skate",
    "Event Hype — Competition Countdown", "Snow Day — Pow Slash Reel",
    "Influencer Collab — @riderjake", "New Drop — Spring Colorway",
    "Behind the Seams — Brand Story", "Archive — Last Season Bestseller",
    "Slopestyle Finals Recap", "Streetwear Lookbook — Urban Edit",
]


def _placement_ctr(placement: str) -> float:
    base = {"Feed": (0.8, 2.5), "Reels": (1.8, 4.5), "Stories": (1.5, 3.8), "Explore": (0.5, 2.2)}
    lo, hi = base[placement]
    return round(random.uniform(lo, hi), 2)


def _placement_cpc(placement: str) -> float:
    base = {"Feed": (1.2, 3.5), "Reels": (0.8, 2.8), "Stories": (0.9, 2.5), "Explore": (1.5, 4.0)}
    lo, hi = base[placement]
    return round(random.uniform(lo, hi), 2)


def get_data() -> dict:
    """Return fake Meta ad performance data."""
    n_ads = random.randint(8, 12)
    ads = []

    for i in range(n_ads):
        placement = random.choice(PLACEMENTS)
        geo = random.choice(GEOS)
        audience = random.choice(AUDIENCES)
        creative = random.choice(CREATIVE_NAMES)

        impressions = random.randint(8_000, 120_000)
        ctr = _placement_ctr(placement)

        # Force 2 bad performers
        if i < 2:
            ctr = round(random.uniform(0.3, 0.7), 2)
            frequency = round(random.uniform(4.5, 8.2), 1)
            roas = round(random.uniform(0.6, 1.1), 2)
            spend = round(random.uniform(150, 400), 2)
        # Force 2 strong performers
        elif i < 4:
            ctr = round(random.uniform(3.2, 4.5), 2)
            frequency = round(random.uniform(1.1, 2.0), 1)
            roas = round(random.uniform(3.8, 5.5), 2)
            spend = round(random.uniform(400, 900), 2)
        else:
            frequency = round(random.uniform(1.5, 3.8), 1)
            roas = round(random.uniform(0.9, 4.2), 2)
            spend = round(random.uniform(80, 600), 2)

        clicks = int(impressions * ctr / 100)
        cpc = _placement_cpc(placement)
        cpm = round((spend / impressions) * 1000, 2)
        conversions = int(clicks * random.uniform(0.02, 0.12))
        revenue = round(conversions * random.uniform(95, 220), 2)

        # Time-of-day — evenings/weekends trend higher
        best_hour = random.choice([18, 19, 20, 21, 22, 14, 15])
        best_day = random.choice(["Saturday", "Sunday", "Friday", "Thursday"])

        ads.append({
            "ad_id": f"AD_{1000 + i}",
            "creative_name": creative,
            "placement": placement,
            "geo": geo,
            "audience": audience,
            "impressions": impressions,
            "reach": int(impressions / max(frequency, 1.0)),
            "clicks": clicks,
            "ctr_pct": ctr,
            "cpc_usd": cpc,
            "cpm_usd": cpm,
            "spend_usd": spend,
            "frequency": frequency,
            "conversions": conversions,
            "revenue_usd": revenue,
            "roas": roas,
            "best_hour": best_hour,
            "best_day": best_day,
            "days_running": random.randint(1, 42),
            "hemisphere": "southern" if any(s in geo for s in ["NZ", "NSW", "VIC", "Australia", "Argentina", "Chile"]) else "northern",
        })

    return {
        "source": "meta_ads",
        "status": "ok",
        "retrieved_at": datetime.utcnow().isoformat(),
        "date_range": {
            "start": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": datetime.utcnow().strftime("%Y-%m-%d"),
        },
        "ads": ads,
        "total_spend_usd": round(sum(a["spend_usd"] for a in ads), 2),
        "total_revenue_usd": round(sum(a["revenue_usd"] for a in ads), 2),
        "blended_roas": round(
            sum(a["revenue_usd"] for a in ads) / max(sum(a["spend_usd"] for a in ads), 0.01), 2
        ),
    }
