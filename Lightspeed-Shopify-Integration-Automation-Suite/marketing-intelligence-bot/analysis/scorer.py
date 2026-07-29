"""
Ranks in-stock products for "advertise this" priority by combining:
- stock health (in stock, not about to sell out to zero from ad-driven demand)
- category trend score (Google Trends)
- seasonal/local relevance (holiday season / midsummer / shoulder season)
- upcoming local events (Dillon Farmers Market, Lake Dillon Arts Festival,
  Small Business Saturday, etc.) — a real, dated hook beats generic season
- current ad performance (don't recommend more spend on a category already
  performing poorly, and flag categories with high CTR but low spend as
  underfunded opportunities)
- online vs. in-store sell-through (Shopify vs. Lightspeed) — used to tag
  each pick as best pushed via "online", "in-store", or "both" campaigns,
  and to flag products that sell in-store but underperform online (usually
  a listing/photo problem, not a demand problem)
"""
import collectors.seasonal_context as seasonal_context

# Weights are a first-pass guess — tune once real performance data exists.
WEIGHTS = {
    "trend": 0.30,
    "season": 0.20,
    "event": 0.15,
    "ad_efficiency": 0.15,
    "stock_health": 0.20,
}

MIN_STOCK_TO_ADVERTISE = 3  # don't advertise something that'll sell out in a day

# Thresholds for tagging channel fit from online-vs-in-store sales mix.
ONLINE_SHARE_FOR_ONLINE_TAG = 0.65   # mostly sells online -> tag "online"
ONLINE_SHARE_FOR_INSTORE_TAG = 0.20   # barely sells online -> tag "in-store"
MIN_SESSIONS_FOR_LISTING_FLAG = 100    # enough traffic that low conversion is meaningful


def _channel_tag(product, online_stats):
    in_store_units = product.get("units_sold_in_store_30d", 0)
    online_units = online_stats.get("units_sold_online_30d", 0)
    total_units = in_store_units + online_units

    if total_units == 0:
        return "both", None

    online_share = online_units / total_units

    listing_flag = None
    sessions = online_stats.get("sessions_30d", 0)
    conversion_rate = online_stats.get("conversion_rate_pct", 0)
    if in_store_units >= 5 and sessions >= MIN_SESSIONS_FOR_LISTING_FLAG and conversion_rate < 3:
        listing_flag = (
            f"sells well in-store ({in_store_units} units/30d) but only "
            f"{conversion_rate}% online conversion despite {sessions} sessions — "
            f"check product photos/description/price online"
        )

    if online_share >= ONLINE_SHARE_FOR_ONLINE_TAG:
        return "online", listing_flag
    if online_share <= ONLINE_SHARE_FOR_INSTORE_TAG:
        return "in-store", listing_flag
    return "both", listing_flag


def score_products(products, trend_scores, ad_performance, current_season,
                    upcoming_events=None, online_performance=None):
    upcoming_events = upcoming_events if upcoming_events is not None else []
    online_performance = online_performance if online_performance is not None else {}
    scored = []
    for p in products:
        if p["qty_in_stock"] < MIN_STOCK_TO_ADVERTISE:
            continue  # never advertise near-out-of-stock items

        category = p["category"]
        trend_score = trend_scores.get(category, 50)
        season_boost = seasonal_context.get_season_boost(category, current_season)
        ad_stats = ad_performance.get(category, {})
        ctr = ad_stats.get("ctr_pct", 0) or 0

        matching_events = [e for e in upcoming_events if category in e.get("relevant_categories", [])]

        stock_health = min(p["qty_in_stock"] / max(p["reorder_point"] * 3, 1), 1.0) * 100
        season_component = 100 if season_boost else 40
        event_component = 100 if matching_events else 30
        ad_efficiency_component = min(ctr * 20, 100)  # scale CTR% into 0-100ish

        composite = (
            trend_score * WEIGHTS["trend"]
            + season_component * WEIGHTS["season"]
            + event_component * WEIGHTS["event"]
            + ad_efficiency_component * WEIGHTS["ad_efficiency"]
            + stock_health * WEIGHTS["stock_health"]
        )

        online_stats = online_performance.get(p["sku"], {})
        channel, listing_flag = _channel_tag(p, online_stats)

        reasons = []
        if matching_events:
            reasons.append(f"{matching_events[0]['name']} coming up ({matching_events[0]['start'].strftime('%b %-d')})")
        if season_boost:
            reasons.append(f"in-season right now ({current_season.replace('_', ' ')})")
        if trend_score >= 65:
            reasons.append(f"trending (search interest {trend_score}/100)")
        if ctr >= 2:
            reasons.append(f"strong ad CTR ({ctr}%) — underfunded opportunity")
        if not reasons:
            reasons.append("steady baseline performer")

        scored.append({
            **p,
            "trend_score": trend_score,
            "season_boost": season_boost,
            "ad_ctr_pct": ctr,
            "channel": channel,
            "listing_flag": listing_flag,
            "online_stats": online_stats,
            "composite_score": round(composite, 1),
            "reasons": reasons,
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored


def top_picks(scored_products, n=5):
    return scored_products[:n]


def listing_flags(scored_products):
    """Products that sell well in-store but underperform online — worth a
    listing/photo fix rather than more ad spend."""
    return [p for p in scored_products if p.get("listing_flag")]
