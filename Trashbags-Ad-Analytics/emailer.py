# emailer.py — format analysis as HTML email and send via Gmail or save to file
import os
import json
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import DEMO_MODE, GMAIL_RECIPIENT, GMAIL_CREDENTIALS_PATH

DEMO_OUTPUT_PATH = "demo_email_output.html"


def _section_header(title: str, color: str = "#1a1a2e") -> str:
    return f"""
    <tr><td style="padding: 0;">
      <div style="background:{color};color:#ffffff;font-size:15px;font-weight:700;
                  padding:12px 20px;margin-top:24px;border-radius:6px 6px 0 0;
                  letter-spacing:0.5px;">
        {title}
      </div>
    </td></tr>"""


def _card(content: str, bg: str = "#f8f9fc") -> str:
    return f"""
    <tr><td style="padding:0 0 2px 0;">
      <div style="background:{bg};padding:14px 20px;border-left:4px solid #e2e8f0;
                  font-size:13px;color:#2d3748;line-height:1.6;">
        {content}
      </div>
    </td></tr>"""


def _badge(text: str, color: str = "#4a5568") -> str:
    return f'<span style="display:inline-block;background:{color};color:#fff;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;margin-right:6px;">{text}</span>'


def _metric(label: str, value: str) -> str:
    return f'<span style="margin-right:18px;"><strong style="color:#2b6cb0;">{value}</strong> <span style="color:#718096;font-size:12px;">{label}</span></span>'


def build_html(dataset: dict, analysis: dict, demo: bool = True) -> str:
    now = datetime.utcnow()
    date_str = now.strftime("%B %d, %Y")
    demo_badge = " [DEMO]" if demo else ""
    subject_line = f"Weekly Ad Performance Summary — {date_str}{demo_badge}"

    a = analysis.get("analysis", {})
    ads_data = dataset.get("sources", {}).get("meta_ads", {})
    total_spend = ads_data.get("total_spend_usd", 0)
    total_revenue = ads_data.get("total_revenue_usd", 0)
    blended_roas = ads_data.get("blended_roas", 0)
    source_errors = dataset.get("source_errors", [])

    # ── Section 1: Ad Performance ──────────────────────────────────────────
    top_placements_html = ""
    for p in a.get("top_placements", [])[:3]:
        ctr_str = "{:.2f}%".format(p.get("ctr", 0))
        cpc_str = "${:.2f}".format(p.get("cpc", 0))
        roas_str = "{:.1f}x".format(p.get("roas", 0))
        top_placements_html += _card(
            f"{_badge(p.get('placement',''), '#2f855a')}"
            f"{_metric('CTR', ctr_str)}"
            f"{_metric('CPC', cpc_str)}"
            f"{_metric('ROAS', roas_str)}"
            f"<br><em style='color:#4a5568;font-size:12px;'>{p.get('verdict','')}</em>"
        )

    top_geos_html = ""
    for g in a.get("top_geos", [])[:4]:
        hemi_color = "#2b6cb0" if g.get("hemisphere") == "northern" else "#c05621"
        roas_str = "{:.1f}x".format(g.get("roas", 0))
        top_geos_html += _card(
            f"{_badge(g.get('geo',''), hemi_color)}"
            f"{_metric('ROAS', roas_str)}"
            f"<span style='color:#718096;font-size:12px;'>{g.get('key_metric','')}</span>"
        )

    freq_alerts_html = ""
    for f in a.get("frequency_alerts", []):
        freq_alerts_html += _card(
            f"{_badge('⚠ HIGH FREQ', '#c53030')}"
            f"<strong>{f.get('creative','')}</strong> — Frequency: {f.get('frequency',0):.1f}x"
            f"<br><em style='font-size:12px;color:#4a5568;'>{f.get('recommendation','')}</em>",
            bg="#fff5f5"
        )

    worst_html = ""
    for p in a.get("worst_placements", [])[:2]:
        worst_html += _card(
            f"{_badge(p.get('placement',''), '#742a2a')}"
            f"CTR: {p.get('ctr',0):.2f}% — {p.get('reason','')}",
            bg="#fff5f5"
        )

    # ── Section 2: Market Conditions ──────────────────────────────────────
    hs = a.get("hemisphere_status", {})
    hemi_html = _card(
        f"{_badge('NORTHERN', '#2b6cb0')} {hs.get('northern','')}&nbsp;&nbsp;"
        f"{_badge('SOUTHERN', '#c05621')} {hs.get('southern','')}<br>"
        f"<em style='font-size:12px;color:#4a5568;'>{hs.get('focus','')}</em>"
    )

    trends_html = ""
    for t in a.get("trending_searches", [])[:5]:
        wow = t.get("wow_change_pct", 0)
        color = "#276749" if wow >= 0 else "#742a2a"
        trends_html += _card(
            f"<strong>{t.get('term_or_city','')}</strong>"
            f"&nbsp;<span style='color:{color};font-weight:700;'>{'+' if wow >= 0 else ''}{wow:.1f}% WoW</span>"
            f"<br><em style='font-size:12px;color:#4a5568;'>{t.get('action','')}</em>"
        )

    snow = a.get("snow_conditions", {})
    snow_html = _card(
        f"{_badge('BEST CONDITIONS', '#276749')} {', '.join(snow.get('best_regions', [])[:3])}<br>"
        f"{_badge('LOW PRIORITY', '#742a2a')} {', '.join(snow.get('worst_regions', [])[:2])}<br>"
        f"<em style='font-size:12px;color:#4a5568;'>{snow.get('opportunity_note','')}</em>"
    )

    events_html = ""
    for e in a.get("upcoming_events", []):
        urgency_color = "#c53030" if e.get("days_until", 99) <= 14 else "#d69e2e"
        days_label = "{} DAYS".format(e.get("days_until", "?"))
        tier = e.get("tier", "")
        tier_color = "#553c9a" if tier == "mega" else "#2c7a7b" if tier == "major" else "#718096"
        tier_badge = _badge(tier.upper(), tier_color) if tier else ""
        host = e.get("host", "")
        host_str = f" · <em style='font-size:11.5px;color:#a0aec0;'>{host}</em>" if host else ""
        events_html += _card(
            f"{_badge(days_label, urgency_color)}{tier_badge}"
            f"<strong>{e.get('event','')}</strong> - {e.get('location','')} - {e.get('date','')}{host_str}<br>"
            f"<em style='font-size:12px;color:#4a5568;'>{e.get('action','')}</em>"
        )

    # ── Section 3: Competitor Activity ──────────────────────────────────
    gaps_html = ""
    for g in a.get("competitor_gaps", [])[:4]:
        urgency_color = "#276749" if g.get("urgency") == "high" else "#2b6cb0"
        gaps_html += _card(
            f"{_badge('GAP', urgency_color)}<strong>{g.get('market','')}</strong><br>"
            f"<em style='font-size:12px;color:#4a5568;'>{g.get('reason','')}</em>"
        )

    comp_creatives_html = ""
    for c in a.get("long_running_competitor_creatives", [])[:3]:
        longevity_label = "{}d running".format(c.get("longevity_days", 0))
        comp_creatives_html += _card(
            f"{_badge(longevity_label, '#744210')}"
            f"<strong>{c.get('brand','')}</strong><br>"
            f"<em style='font-size:12px;color:#4a5568;'>{c.get('insight','')}</em>",
            bg="#fffbeb"
        )

    oversaturated_html = ""
    for o in a.get("oversaturated_markets", [])[:3]:
        oversaturated_html += _card(
            f"{_badge('CROWDED', '#744210')}<strong>{o.get('market','')}</strong> — {o.get('note','')}",
            bg="#fffbeb"
        )

    # ── Section 4A: Existing Ad Recommendations ───────────────────────────
    recs = a.get("existing_ad_recommendations", {})

    def rec_rows(items: list, label: str, color: str) -> str:
        html = ""
        for item in items:
            target = item.get("target", item.get("from", item.get("location", item.get("current", item.get("segment", "")))))
            to = item.get("to", item.get("better", ""))
            reason = item.get("reason", "")
            content = f"{_badge(label, color)}<strong>{target}</strong>"
            if to:
                content += f" → <strong>{to}</strong>"
            content += f"<br><em style='font-size:12px;color:#4a5568;'>{reason}</em>"
            html += _card(content, bg="#f0fff4" if color == "#276749" else "#fff5f5" if color == "#c53030" else "#f8f9fc")
        return html

    existing_recs_html = (
        rec_rows(recs.get("pause", []), "PAUSE", "#c53030") +
        rec_rows(recs.get("keep_running", []), "KEEP RUNNING", "#276749") +
        rec_rows(recs.get("shift_budget", []), "SHIFT BUDGET", "#2b6cb0") +
        rec_rows(recs.get("geo_adjustments", []), "GEO", "#553c9a") +
        rec_rows(recs.get("timing_adjustments", []), "TIMING", "#744210") +
        rec_rows(recs.get("audience_refinements", []), "AUDIENCE", "#2c7a7b")
    )

    # ── Section 4B: New Ad Recommendations ────────────────────────────────
    new_recs = a.get("new_ad_recommendations", {})

    new_recs_html = ""
    for item in new_recs.get("competitor_gaps", []):
        new_recs_html += _card(
            f"{_badge('COMPETITOR GAP', '#276749')}<strong>{item.get('market','')}</strong><br>"
            f"<em style='font-size:12px;color:#4a5568;'>{item.get('insight','')}</em>",
            bg="#f0fff4"
        )
    for item in new_recs.get("park_event_opportunities", []):
        new_recs_html += _card(
            f"{_badge('PARK EVENT', '#553c9a')}<strong>{item.get('event','')}</strong> — {item.get('location','')} — {item.get('date','')}<br>"
            f"Audience: {item.get('audience','')} | Window: {item.get('window','')}"
        )
    for item in new_recs.get("hemisphere_opportunities", []):
        new_recs_html += _card(
            f"{_badge('HEMISPHERE OPP', '#c05621')}<strong>{item.get('location','')}</strong> — {item.get('season_status','')}<br>"
            f"<em style='font-size:12px;color:#4a5568;'>Conditions: {item.get('conditions','')}</em>"
        )
    for item in new_recs.get("new_geo_targets", [])[:4]:
        new_recs_html += _card(
            f"{_badge('NEW GEO', '#2b6cb0')}<strong>{item.get('city','')}</strong><br>"
            f"<em style='font-size:12px;color:#4a5568;'>{item.get('demand_signal','')} | Score: {item.get('combined_score','')}</em>"
        )
    for item in new_recs.get("new_audience_segments", []):
        new_recs_html += _card(
            f"{_badge('NEW AUDIENCE', '#2c7a7b')}<strong>{item.get('segment','')}</strong> — {item.get('fit','')}"
        )
    for item in new_recs.get("new_placements", []):
        new_recs_html += _card(
            f"{_badge('NEW PLACEMENT', '#744210')}<strong>{item.get('placement','')}</strong> — {item.get('opportunity','')}"
        )

    # ── Section 5: Global Snapshot ─────────────────────────────────────────
    gs = a.get("global_snapshot", {})
    snapshot_html = _card(
        f"📈 <strong>Trending Up:</strong> {', '.join(gs.get('trending_up', []))}<br>"
        f"🎿 <strong>Park Events Incoming:</strong> {', '.join(gs.get('park_events_incoming', []))}<br>"
        f"🔵 <strong>Northern Hemisphere:</strong> {gs.get('northern_summary','')}<br>"
        f"🔴 <strong>Southern Hemisphere:</strong> {gs.get('southern_summary','')}<br>"
        f"⏭️ <strong>Next 2–4 Weeks:</strong> {gs.get('next_2_4_weeks_focus','')}<br>"
        f"📉 <strong>Trending Down:</strong> {', '.join(gs.get('trending_down', []))}"
    )

    # ── Error banner ───────────────────────────────────────────────────────
    error_banner = ""
    if source_errors:
        errors_list = "<br>".join(f"• {e}" for e in source_errors)
        error_banner = f"""
        <tr><td style="padding:12px 0 0 0;">
          <div style="background:#fff5f5;border:1px solid #fc8181;border-radius:6px;padding:12px 16px;font-size:12px;color:#742a2a;">
            ⚠ <strong>Data source warnings (partial data used):</strong><br>{errors_list}
          </div>
        </td></tr>"""

    # ── Full HTML assembly ─────────────────────────────────────────────────
    demo_ribbon = (
        '<div style="background:#f6e05e;color:#744210;text-align:center;padding:8px;font-size:12px;font-weight:700;">'
        '⚡ DEMO MODE — All data is simulated. No real ad spend or API credentials used.'
        '</div>' if demo else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject_line}</title>
</head>
<body style="margin:0;padding:0;background:#edf2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
{demo_ribbon}
<div style="max-width:680px;margin:24px auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:28px 28px 20px;color:#fff;">
    <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#90cdf4;margin-bottom:6px;">
      Trashbags Co. — Ad Intelligence
    </div>
    <h1 style="margin:0 0 4px;font-size:20px;font-weight:700;">{subject_line}</h1>
    <div style="font-size:12px;color:#a0aec0;">Generated {now.strftime("%A, %B %d %Y at %H:%M UTC")}</div>
  </div>

  <!-- Summary bar -->
  <div style="background:#2d3748;padding:14px 28px;display:flex;gap:32px;">
    <div style="color:#fff;">
      <div style="font-size:11px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">Total Spend</div>
      <div style="font-size:22px;font-weight:700;">${total_spend:,.2f}</div>
    </div>
    <div style="color:#fff;">
      <div style="font-size:11px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">Revenue</div>
      <div style="font-size:22px;font-weight:700;">${total_revenue:,.2f}</div>
    </div>
    <div style="color:#fff;">
      <div style="font-size:11px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;">Blended ROAS</div>
      <div style="font-size:22px;font-weight:700;color:{'#68d391' if blended_roas >= 2 else '#fc8181'}">{blended_roas:.2f}x</div>
    </div>
  </div>

  <div style="padding:0 20px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">

      {error_banner}

      <!-- SECTION 5 (moved to top) -->
      {_section_header("GLOBAL SNAPSHOT", "#322659")}
      {snapshot_html}

      <!-- SECTION 1 -->
      {_section_header("1 — YOUR AD PERFORMANCE", "#1a365d")}
      {_card("<strong>Top Performing Placements</strong>")}
      {top_placements_html}
      {_card("<strong>Top Performing Geos</strong>")}
      {top_geos_html}
      {_card("<strong>Frequency Alerts — Over-Saturated Audiences</strong>") if freq_alerts_html else ""}
      {freq_alerts_html}
      {_card("<strong>Worst Performing Placements</strong>") if worst_html else ""}
      {worst_html}

      <!-- SECTION 2 -->
      {_section_header("2 — MARKET CONDITIONS", "#1c4532")}
      {_card("<strong>Hemisphere Status</strong>")}
      {hemi_html}
      {_card("<strong>Google Trends — Top Spikes This Week</strong>")}
      {trends_html}
      {_card("<strong>Snow Conditions</strong>")}
      {snow_html}
      {_card("<strong>Upcoming Park Events — Within 3 Weeks</strong>") if events_html else ""}
      {events_html or _card("No events within 3 weeks.", "#f8f9fc")}

      <!-- SECTION 3 -->
      {_section_header("3 — COMPETITOR ACTIVITY", "#1a202c")}
      {_card("<strong>Markets Competitors Are Ignoring</strong>")}
      {gaps_html or _card("No significant gaps detected.")}
      {_card("<strong>Long-Running Competitor Creatives</strong>")}
      {comp_creatives_html or _card("No long-running creatives detected.")}
      {_card("<strong>Oversaturated Markets</strong>")}
      {oversaturated_html or _card("No oversaturation detected.")}

      <!-- SECTION 4A -->
      {_section_header("4A — EXISTING AD RECOMMENDATIONS", "#2a4365")}
      {existing_recs_html or _card("No recommendations this week.")}

      <!-- SECTION 4B -->
      {_section_header("4B — NEW AD RECOMMENDATIONS", "#22543d")}
      {new_recs_html or _card("No new opportunities flagged this week.")}

    </table>
  </div>

  <!-- Footer -->
  <div style="background:#f7fafc;border-top:1px solid #e2e8f0;padding:14px 28px;font-size:11px;color:#a0aec0;text-align:center;">
    Trashbags Co. Ad Intelligence System · Powered by Claude claude-sonnet-4-6 · {'DEMO MODE' if demo else 'LIVE DATA'}
    <br>Read-only — no spend changes are made automatically
  </div>

</div>
</body>
</html>"""

    return html


def send_or_save(html: str, subject: str) -> None:
    if DEMO_MODE:
        output_path = os.path.join(os.path.dirname(__file__), DEMO_OUTPUT_PATH)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ DEMO MODE: Email saved to {output_path}")
        print(f"   Open in browser: file://{os.path.abspath(output_path)}")
        return

    # Live Gmail send via OAuth2
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle

        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        token_path = "credentials/gmail_token.pickle"
        creds = None

        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        service = build("gmail", "v1", credentials=creds)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["To"] = GMAIL_RECIPIENT
        msg.attach(MIMEText(html, "html"))

        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw_msg}).execute()
        print(f"✅ Email sent to {GMAIL_RECIPIENT}")

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        raise


def deliver(dataset: dict, analysis: dict) -> None:
    now = datetime.utcnow()
    date_str = now.strftime("%B %d, %Y")
    demo_badge = " [DEMO]" if DEMO_MODE else ""
    subject = f"Weekly Ad Performance Summary — {date_str}{demo_badge}"

    print("[emailer] Building HTML email...")
    html = build_html(dataset, analysis, demo=DEMO_MODE)
    send_or_save(html, subject)
