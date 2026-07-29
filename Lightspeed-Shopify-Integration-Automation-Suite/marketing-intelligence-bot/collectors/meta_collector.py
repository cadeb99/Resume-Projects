"""
Meta (Facebook/Instagram) ad performance per product category. Demo mode
generates randomized-but-plausible dummy metrics; live mode will call the
Meta Marketing API once META_ACCESS_TOKEN / META_AD_ACCOUNT_ID exist.
"""
import random
import config


def get_ad_performance(categories):
    if config.DEMO_MODE:
        return _fetch_mock(categories)
    return _fetch_live(categories)


def _fetch_mock(categories):
    performance = {}
    for category in categories:
        impressions = random.randint(500, 8000)
        clicks = int(impressions * random.uniform(0.005, 0.04))
        spend = round(random.uniform(5, 80), 2)
        performance[category] = {
            "impressions": impressions,
            "clicks": clicks,
            "ctr_pct": round((clicks / impressions) * 100, 2) if impressions else 0,
            "spend_usd": spend,
            "cpc_usd": round(spend / clicks, 2) if clicks else None,
        }
    return performance


def _fetch_live(categories):
    """
    TODO once credentials exist: pull campaign/adset insights from Meta
    Marketing API filtered/tagged by product category, map to same shape
    as _fetch_mock.
    """
    raise NotImplementedError(
        "Live Meta integration not yet wired. Set DEMO_MODE=True in "
        "config.py, or implement _fetch_live() with real API credentials."
    )
