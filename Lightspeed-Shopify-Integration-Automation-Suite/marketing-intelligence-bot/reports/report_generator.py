"""
Builds the weekly HTML report from aggregated data. Same pattern as the prior
snowpants report: one self-contained HTML string, no external assets, safe to
email directly.
"""
from datetime import date


def build_html_report(context):
    top_products = context["top_products"]
    content_plan = context["content_plan"]
    ad_recommendations = context["ad_recommendations"]
    weather = context["weather"]
    season = context["season"].replace("_", " ").title()
    store_name = context["store_name"]
    upcoming_events = context.get("upcoming_events", [])
    listing_flags = context.get("listing_flags", [])

    channel_badge = {
        "online": "🖥️ Online", "in-store": "🏬 In-Store", "both": "🔁 Both",
    }

    rows = "".join(
        f"""
        <tr>
          <td>{p['name']}</td>
          <td>{p['store']}</td>
          <td>{channel_badge.get(p.get('channel'), p.get('channel', ''))}</td>
          <td>{p['qty_in_stock']}</td>
          <td>{p['composite_score']}</td>
          <td>{'; '.join(p['reasons'])}</td>
        </tr>"""
        for p in top_products
    )

    listing_flags_html = (
        "".join(f"<li><strong>{p['name']}</strong> ({p['sku']}) — {p['listing_flag']}</li>"
                for p in listing_flags)
        if listing_flags else "<li>None flagged this run.</li>"
    )

    format_badge = {"Reel": "🎬 Reel", "Carousel": "🖼️ Carousel", "Post": "📷 Post", "Story": "⏱️ Story"}
    content_plan_html = "".join(
        f"""
        <div style="border:1px solid #ddd; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
          <div style="font-weight:bold; color:#2c3e50;">{format_badge.get(item['format'], item['format'])} — {item['title']}</div>
          <div style="font-size:13px; margin-top:4px;"><em>Concept:</em> {item['concept']}</div>
          <div style="font-size:12px; color:#666; margin-top:4px;"><em>Why:</em> {item['why']}</div>
          <div style="font-size:13px; margin-top:6px;"><em>Caption starter:</em> "{item['caption']}"</div>
        </div>"""
        for item in content_plan
    )

    def _ad_row(a):
        badge = format_badge.get(a["format"], a["format"])
        if a["boost"]:
            return (
                f"<li><strong style=\"color:#2e7d32;\">▲ BOOST</strong> — {badge} — {a['title']}<br>"
                f"<span style=\"font-size:12px; color:#555;\">{a['reason']}</span><br>"
                f"<span style=\"font-size:12px; color:#555;\"><em>Targeting:</em> {a['targeting']}</span></li>"
            )
        return (
            f"<li><strong style=\"color:#999;\">— ORGANIC ONLY</strong> — {badge} — {a['title']}<br>"
            f"<span style=\"font-size:12px; color:#555;\">{a['reason']}</span></li>"
        )

    ad_html = (
        "".join(_ad_row(a) for a in ad_recommendations)
        if ad_recommendations else "<li>No posts scored high enough to recommend paid spend this week.</li>"
    )

    events_html = (
        "".join(
            f"<li><strong>{e['name']}</strong> — {e['start'].strftime('%b %-d')}"
            f"{'' if e['start'] == e['end'] else ' to ' + e['end'].strftime('%b %-d')}</li>"
            for e in upcoming_events
        )
        if upcoming_events else "<li>No local events in the next 14 days.</li>"
    )

    weather_line = (
        f"Avg high {weather['avg_high_f']}°F this week, "
        f"{weather['total_snowfall_in']}in snow expected."
        if weather["avg_high_f"] is not None
        else "Weather data unavailable this run."
    )

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #222; max-width: 700px; margin: auto;">
      <h1 style="color:#2c3e50;">{store_name} — Weekly Marketing Intelligence</h1>
      <p><strong>Week of:</strong> {date.today().isoformat()} &nbsp;|&nbsp;
         <strong>Season context:</strong> {season} &nbsp;|&nbsp; {weather_line}</p>

      <h2>Advertise This Week</h2>
      <p style="font-size:13px; color:#555;">Channel tag reflects online (Shopify) vs. in-store
        (Lightspeed) sell-through mix over the last 30 days — target the campaign accordingly.</p>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%;">
        <tr style="background:#f2f2f2;">
          <th>Product</th><th>Store</th><th>Channel</th><th>In Stock</th><th>Score</th><th>Why</th>
        </tr>
        {rows}
      </table>

      <h2>Online Listing Flags</h2>
      <p style="font-size:13px; color:#555;">Sells well in-store but underperforms online despite
        real traffic — likely a photo/description/price issue, not a demand issue.</p>
      <ul>{listing_flags_html}</ul>

      <h2>Upcoming Local Events (next 14 days)</h2>
      <ul>{events_html}</ul>

      <h2>This Week's Content Plan</h2>
      <p style="font-size:13px; color:#555;">What to actually shoot and post this week, and the data
        behind each pick — a guide, not just captions.</p>
      {content_plan_html}

      <h2>Which Posts to Run Ads On</h2>
      <p style="font-size:13px; color:#555;">Not new ad creative — a recommendation on which of this
        week's planned posts (above) are worth boosting with paid Meta spend, and which should stay organic.</p>
      <ul>{ad_html}</ul>

      <p style="color:#888; font-size:12px;">
        Generated automatically — demo mode data may be randomized/mocked.
        Review before publishing any content.
      </p>
    </body>
    </html>
    """
