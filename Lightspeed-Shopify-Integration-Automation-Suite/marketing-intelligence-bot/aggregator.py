"""
Wires the pipeline together: collectors -> scorer -> content generator -> report.
"""
import config
import collectors.lightspeed_collector as lightspeed_collector
import collectors.shopify_collector as shopify_collector
import collectors.trends_collector as trends_collector
import collectors.weather_collector as weather_collector
import collectors.meta_collector as meta_collector
import collectors.seasonal_context as seasonal_context
import analysis.scorer as scorer
import analysis.content_generator as content_generator


def run_pipeline():
    products = lightspeed_collector.get_inventory()
    categories = sorted({p["category"] for p in products})

    online_performance = shopify_collector.get_online_performance()
    trend_scores = trends_collector.get_trend_scores(categories)
    weather = weather_collector.get_weather_context()
    ad_performance = meta_collector.get_ad_performance(categories)
    current_season = seasonal_context.get_current_season()
    upcoming_events = seasonal_context.get_upcoming_events()

    scored = scorer.score_products(
        products, trend_scores, ad_performance, current_season,
        upcoming_events, online_performance,
    )
    top_products = scorer.top_picks(scored, n=5)
    listing_flags = scorer.listing_flags(scored)

    content_plan = content_generator.generate_content_plan(top_products, upcoming_events, listing_flags)
    ad_recommendations = content_generator.generate_ad_recommendations(content_plan, top_products)

    return {
        "store_name": config.STORE_NAME,
        "season": current_season,
        "upcoming_events": upcoming_events,
        "weather": weather,
        "all_scored_products": scored,
        "top_products": top_products,
        "listing_flags": listing_flags,
        "content_plan": content_plan,
        "ad_recommendations": ad_recommendations,
        "trend_scores": trend_scores,
        "ad_performance": ad_performance,
        "online_performance": online_performance,
    }
