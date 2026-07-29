"""
Builds a weekly social content PLAN, not just captions — a guide telling
Kathleen/Decker what to actually shoot and post this week (Reel, Carousel,
single Post, or Story), and why, based on what the data is showing:
- the single hottest mover this week -> Reel (best format for a trending item)
- the next tier of top picks, grouped -> Carousel roundup
- an upcoming local event -> Story/Post tied to that date
- a product that sells in-store but flops online -> Post calling out that it
  needs better photos (the listing_flag from analysis/scorer.py)
- store heritage / evergreen -> Post

Each idea includes: format, a concrete concept for what to film/shoot, the
data reason it made the list, and a caption starter, plus the SKUs involved
so ad-boost recommendations can reference back to specific posts.

Rather than generating separate ad copy, generate_ad_recommendations()
decides WHICH of the posts above are worth putting paid Meta spend behind —
same pattern as the prior snowpants ad automation (recommend where budget
goes, don't invent new creative for it).
"""
import datetime
import config


def _reason_text(product):
    return product["reasons"][0] if product.get("reasons") else "a customer favorite"


def _event_for_product(product, upcoming_events):
    category = product.get("category")
    for event in upcoming_events:
        if category in event.get("relevant_categories", []):
            return event
    return None


def generate_content_plan(top_products, upcoming_events=None, listing_flags=None):
    """Returns an ordered list of content ideas for the week, each:
    {format, title, concept, why, caption}."""
    upcoming_events = upcoming_events or []
    listing_flags = listing_flags or []
    plan = []
    used_skus = set()

    if not top_products:
        return plan

    # 1. REEL — the single highest-scored product this week. Reels are the
    # best format for capturing a genuine trend/demand spike, so lead with it.
    hero = top_products[0]
    hero_reason = _reason_text(hero)
    plan.append({
        "format": "Reel",
        "title": f"This week's mover: {hero['name']}",
        "concept": (
            f"15-20s Reel — quick unboxing or in-hand demo of {hero['name']} on the sales floor. "
            f"Open on the product, show it in use/being played with in the first 2 seconds, "
            f"text overlay naming it, end on a shop-the-look CTA."
        ),
        "why": f"Top-ranked pick this week ({hero['composite_score']}/100) — {hero_reason}.",
        "caption": (
            f"This week's top pick at {hero['store']}: {hero['name']}. "
            f"{hero_reason[0].upper() + hero_reason[1:]}. Come see it in Frisco or shop online!"
        ),
        "skus": [hero["sku"]],
    })
    used_skus.add(hero["sku"])

    # 2. CAROUSEL — the next tier of top picks, grouped into a themed roundup.
    roundup_products = [p for p in top_products[1:4] if p["sku"] not in used_skus]
    if roundup_products:
        names = ", ".join(p["name"] for p in roundup_products)
        slide_lines = "; ".join(
            f"slide {i+2}: {p['name']} — {_reason_text(p)}" for i, p in enumerate(roundup_products)
        )
        plan.append({
            "format": "Carousel",
            "title": f"Roundup: {len(roundup_products)} picks worth featuring this week",
            "concept": (
                f"{len(roundup_products) + 1}-slide carousel. Slide 1: bold cover text "
                f"(\"This week at Stork & Bear / Around the World Toys\"). "
                f"{slide_lines}. One product per slide, consistent flat-lay or shelf shot style."
            ),
            "why": "Next-highest scoring products this week — grouping them into one post covers more ground than separate posts and performs well as a swipeable format.",
            "caption": f"A few things we're loving in the shop this week: {names}. Swipe through →",
            "skus": [p["sku"] for p in roundup_products],
        })
        used_skus.update(p["sku"] for p in roundup_products)

    # 3. STORY/POST — tied to a real upcoming local event, if one matches
    # any top product's category.
    event_product = None
    matched_event = None
    for p in top_products:
        event = _event_for_product(p, upcoming_events)
        if event:
            event_product = p
            matched_event = event
            break
    if matched_event:
        days_out = (matched_event["start"] - datetime.date.today()).days
        timing = "this weekend" if 0 <= days_out <= 3 else f"on {matched_event['start'].strftime('%b %-d')}"
        plan.append({
            "format": "Story",
            "title": f"{matched_event['name']} countdown",
            "concept": (
                f"Story sticker countdown to {matched_event['name']} ({timing}). "
                f"Pair with a quick shot of {event_product['name']} or the storefront decorated for it. "
                f"Use the event location sticker if it's at a specific Frisco/Summit County venue."
            ),
            "why": f"{matched_event['name']} is coming up {timing} — real local foot-traffic driver, not a generic seasonal post.",
            "caption": f"{matched_event['name']} is {timing}! Stop by before or after — we'll be open on Main St.",
            "skus": [event_product["sku"]],
        })

    # 4. POST — a listing flag: sells in-store, underperforms online despite
    # traffic. The fix is better content, so turn the flag itself into a
    # concrete shoot request instead of leaving it as a data footnote.
    if listing_flags:
        flagged = listing_flags[0]
        plan.append({
            "format": "Post",
            "title": f"Reshoot needed: {flagged['name']}",
            "concept": (
                f"Styled product photo (natural light, on a kid or with hands-on play, not just on a shelf) "
                f"for {flagged['name']}. Current online listing is getting traffic but not converting — "
                f"a stronger lifestyle shot is the fix, not more ad spend."
            ),
            "why": flagged.get("listing_flag", "Sells in-store but underperforms online despite traffic."),
            "caption": f"{flagged['name']} — a customer favorite in-store, now easier to shop online too!",
            "skus": [flagged["sku"]],
        })

    # 5. POST — evergreen heritage angle using whichever top product hasn't
    # been used yet, so the plan doesn't repeat the same product twice.
    remaining = [p for p in top_products if p["sku"] not in used_skus]
    if remaining:
        p = remaining[0]
        reason = _reason_text(p)
        plan.append({
            "format": "Post",
            "title": f"Brand story tie-in: {p['name']}",
            "concept": (
                f"Single photo post, {p['name']} shot in-store with a bit of the shop visible in the "
                f"background (shelving, signage) to reinforce it's a real local storefront, not just an online listing."
            ),
            "why": f"Established {config.STORE_ESTABLISHED_YEAR} — heritage angle performs well as a trust-building post between product-first content.",
            "caption": (
                f"Serving Summit County families since {config.STORE_ESTABLISHED_YEAR} — "
                f"{p['name']} is in stock now at {p['store']}. {reason[0].upper() + reason[1:]}."
            ),
            "skus": [p["sku"]],
        })

    return plan


# Minimum composite score for a post to be worth paid spend at all — below
# this, put the effort into organic reach instead of boosting.
MIN_SCORE_TO_BOOST = 55

TARGETING_BY_CHANNEL = {
    "online": "Meta ad, Shopify checkout as destination — target Summit County + Front Range drive-market (Denver metro) parents",
    "both": "Meta ad, Shopify checkout as destination — target Summit County locals + Front Range drive-market parents",
}


def generate_ad_recommendations(content_plan, top_products):
    """Decides which of this week's PLANNED POSTS are worth boosting with
    paid Meta spend, instead of generating separate ad creative. Returns
    a list of {format, title, boost_reason, targeting, skip} — `skip`
    entries explain why an in-store-only post was left organic-only."""
    products_by_sku = {p["sku"]: p for p in top_products}
    recommendations = []

    for item in content_plan:
        skus = item.get("skus", [])
        involved = [products_by_sku[s] for s in skus if s in products_by_sku]
        if not involved:
            continue

        best = max(involved, key=lambda p: p["composite_score"])
        channels = {p.get("channel") for p in involved}

        if best["composite_score"] < MIN_SCORE_TO_BOOST:
            continue

        if channels == {"in-store"}:
            recommendations.append({
                "format": item["format"],
                "title": item["title"],
                "boost": False,
                "reason": (
                    f"{'; '.join(p['name'] for p in involved)} sells in-store, not online — "
                    f"a Meta ad here would drive clicks with nowhere local to convert. "
                    f"Keep this organic and let foot traffic do the work."
                ),
                "targeting": None,
            })
            continue

        channel = "both" if "both" in channels or len(channels) > 1 else next(iter(channels))
        ctr_note = f", CTR {best['ad_ctr_pct']}%" if best.get("ad_ctr_pct") else ""
        recommendations.append({
            "format": item["format"],
            "title": item["title"],
            "boost": True,
            "reason": (
                f"Score {best['composite_score']}/100{ctr_note} and sells "
                f"{'both channels' if channel == 'both' else channel} — worth putting spend behind."
            ),
            "targeting": TARGETING_BY_CHANNEL.get(channel, TARGETING_BY_CHANNEL["online"]),
        })

    return recommendations
