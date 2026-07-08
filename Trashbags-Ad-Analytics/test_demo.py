# test_demo.py — generate a demo email with mock analysis (no API key needed)
from aggregator import aggregate
from emailer import build_html

MOCK_ANALYSIS = {
    "status": "ok",
    "analysis": {
        "top_placements": [
            {"placement": "Reels", "ctr": 3.8, "cpc": 1.20, "roas": 4.2, "verdict": "Reels dominating CTR - double down on short-form video creative."},
            {"placement": "Stories", "ctr": 2.9, "cpc": 1.55, "roas": 3.1, "verdict": "Strong for 18-24 park audience, test swipe-up CTAs."},
        ],
        "worst_placements": [
            {"placement": "Feed - Archive Flat Lay", "ctr": 0.4, "reason": "Frequency at 6.8x, audience burned out on static creative."},
        ],
        "top_geos": [
            {"geo": "Queenstown NZ", "roas": 4.8, "hemisphere": "southern", "key_metric": "Peak season, strong snowfall, 0 competitors."},
            {"geo": "Mammoth CA", "roas": 3.9, "hemisphere": "northern", "key_metric": "Grand Prix event in 12 days - pre-event hype window."},
        ],
        "top_audiences": [
            {"audience": "18-24 Park Riders", "ctr": 3.9, "roas": 4.1, "best_time": "Fri-Sun 7-10pm"},
        ],
        "frequency_alerts": [
            {"ad_id": "AD_1000", "creative": "Baggy Pants Product Flat Lay", "frequency": 6.8,
             "recommendation": "Pause immediately. Refresh creative or exclude this audience for 14 days."},
        ],
        "hemisphere_status": {
            "northern": "OFF SEASON", "southern": "PEAK SEASON",
            "focus": "Southern hemisphere is the primary revenue opportunity right now. Shift 60-70% of budget south."
        },
        "trending_searches": [
            {"term_or_city": "Queenstown NZ", "wow_change_pct": 48.2, "action": "No current targeting here - add immediately."},
            {"term_or_city": "snowpants baggy", "wow_change_pct": 32.1, "action": "Align creative copy to match search intent."},
            {"term_or_city": "Wanaka NZ", "wow_change_pct": 38.0, "action": "Zero competitors, launch test campaign."},
        ],
        "snow_conditions": {
            "best_regions": ["Cardrona NZ", "Valle Nevado Chile", "Coronet Peak NZ"],
            "worst_regions": ["Park City UT", "Mammoth CA"],
            "opportunity_note": "Southern hemisphere conditions excellent - Cardrona and Valle Nevado reporting 28+ inch weeks."
        },
        "upcoming_events": [
            {"event": "Corralco Slopestyle Open", "location": "Corralco Chile", "date": "2026-07-05",
             "days_until": 16, "action": "Launch geo-targeted Reels campaign now. 1500-3500 expected attendance."},
            {"event": "Cardrona Spring Rail Jam", "location": "Cardrona NZ", "date": "2026-07-12",
             "days_until": 23, "action": "Begin pre-event awareness in Queenstown/Wanaka DMA in 1 week."},
        ],
        "competitor_gaps": [
            {"market": "Wanaka NZ", "reason": "Strong search demand, peak season, zero competitor ads found.", "urgency": "high"},
            {"market": "Bariloche Argentina", "reason": "One competitor at low spend. Strong organic interest.", "urgency": "medium"},
        ],
        "long_running_competitor_creatives": [
            {"brand": "RideCo Outerwear", "longevity_days": 38, "insight": "38-day Reels still running = proven performer. Study hook and format."},
        ],
        "oversaturated_markets": [
            {"market": "Park City UT", "note": "3 competitors active, poor snow, off season. Avoid spend this week."},
        ],
        "existing_ad_recommendations": {
            "pause": [
                {"target": "Baggy Pants Product Flat Lay - Feed", "reason": "Frequency 6.8x, CTR 0.4%, ROAS 0.8x. Audience exhausted."},
            ],
            "keep_running": [
                {"target": "Park Riding Edit - Slow Mo Rails - Reels", "reason": "CTR 3.8%, ROAS 4.2x, frequency 1.4x. Scale budget 20%."},
            ],
            "shift_budget": [
                {"from": "Feed static creative", "to": "Reels - southern hemisphere targeting",
                 "reason": "Peak season south, 3x ROAS differential favoring Reels."},
            ],
            "geo_adjustments": [
                {"location": "Queenstown NZ", "action": "Increase", "reason": "48% WoW spike, peak season, no competitors, excellent snow."},
                {"location": "Park City UT", "action": "Pause", "reason": "Off season, poor conditions, 3 competitors, ROAS 0.9x."},
            ],
            "timing_adjustments": [
                {"current": "Flat 24/7 delivery", "better": "Fri-Sun 6pm-11pm weighted",
                 "reason": "Park rider 18-24 audience 2.8x more likely to convert evenings/weekends."},
            ],
            "audience_refinements": [
                {"segment": "Lookalike - Past Purchasers", "action": "Expand to 3% lookalike",
                 "reason": "Current 1% showing saturation at 3.2 frequency. Room to scale."},
            ]
        },
        "new_ad_recommendations": {
            "competitor_gaps": [
                {"market": "Wanaka NZ", "insight": "Zero competitors, peak season, 38% WoW growth. High-intent park audience."},
            ],
            "park_event_opportunities": [
                {"event": "Corralco Slopestyle Open", "location": "Corralco Chile", "date": "2026-07-05",
                 "audience": "Park Riders 16-28, South American ski market", "window": "June 17 - July 12"},
            ],
            "hemisphere_opportunities": [
                {"location": "Perisher NSW Australia", "season_status": "PEAK SEASON",
                 "conditions": "Good - 14in last 7 days, 65in base depth"},
            ],
            "new_geo_targets": [
                {"city": "Wanaka NZ", "demand_signal": "+38% WoW search, 0 competitors", "combined_score": "Very High"},
                {"city": "Santiago Chile", "demand_signal": "Event spillover from Corralco, growing ski market", "combined_score": "High"},
            ],
            "new_audience_segments": [
                {"segment": "Streetwear 18-28 - Auckland NZ", "fit": "Southern peak + streetwear crossover. NZ market under-indexed."},
            ],
            "new_placements": [
                {"placement": "Instagram Explore - Southern Hemisphere",
                 "opportunity": "Explore CTR 20% above Feed for discovery. Not currently active south."},
            ]
        },
        "global_snapshot": {
            "trending_up": ["Queenstown NZ +48%", "Valle Nevado Chile +41%", "Cardrona NZ +35%", "Wanaka NZ +38%"],
            "park_events_incoming": ["Corralco Slopestyle (Chile, 16 days)", "Cardrona Rail Jam (NZ, 23 days)"],
            "northern_summary": "Off season. Streetwear angle only. NYC/LA/Tokyo minimal maintenance spend.",
            "southern_summary": "PEAK SEASON. Excellent snow NZ + Chile. 2 events within 3 weeks. Full budget push south.",
            "next_2_4_weeks_focus": "Southern hemisphere all-in. Corralco event geo push. Wanaka new launch. Scale Reels.",
            "trending_down": ["Park City UT", "Mammoth CA", "Aspen CO (off season)"]
        }
    }
}

if __name__ == "__main__":
    print("Aggregating demo data...")
    dataset = aggregate()
    print("Building email HTML...")
    html = build_html(dataset, MOCK_ANALYSIS, demo=True)
    output_path = "demo_email_output.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nDemo email saved to: {output_path}")
    print(f"File size: {len(html):,} bytes")
    print(f"\nOpen in browser: file:///{output_path.replace(chr(92), '/')}")
