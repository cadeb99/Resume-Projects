# collectors/meta_ads.py — live Meta Marketing API collector
import requests
from datetime import datetime, timedelta
from config import META_ACCESS_TOKEN, META_AD_ACCOUNT_ID


def get_data() -> dict:
    """Fetch real ad performance from Meta Marketing API."""
    try:
        base_url = f"https://graph.facebook.com/v19.0/act_{META_AD_ACCOUNT_ID}/insights"
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        params = {
            "access_token": META_ACCESS_TOKEN,
            "fields": (
                "ad_id,ad_name,impressions,reach,clicks,ctr,cpc,cpm,spend,"
                "frequency,actions,action_values,purchase_roas"
            ),
            "level": "ad",
            "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
            "breakdowns": "placement,region",
            "limit": 500,
        }

        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        raw = resp.json()

        ads = []
        for row in raw.get("data", []):
            roas_val = 0.0
            for r in row.get("purchase_roas", []):
                roas_val = float(r.get("value", 0))

            conversions = 0
            revenue = 0.0
            for action in row.get("actions", []):
                if action.get("action_type") == "purchase":
                    conversions = int(action.get("value", 0))
            for av in row.get("action_values", []):
                if av.get("action_type") == "purchase":
                    revenue = float(av.get("value", 0))

            ads.append({
                "ad_id": row.get("ad_id", ""),
                "creative_name": row.get("ad_name", ""),
                "placement": row.get("placement", "Unknown"),
                "geo": row.get("region", "Unknown"),
                "impressions": int(row.get("impressions", 0)),
                "reach": int(row.get("reach", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr_pct": float(row.get("ctr", 0)),
                "cpc_usd": float(row.get("cpc", 0)),
                "cpm_usd": float(row.get("cpm", 0)),
                "spend_usd": float(row.get("spend", 0)),
                "frequency": float(row.get("frequency", 1)),
                "conversions": conversions,
                "revenue_usd": revenue,
                "roas": roas_val,
            })

        return {
            "source": "meta_ads",
            "status": "ok",
            "retrieved_at": datetime.utcnow().isoformat(),
            "date_range": {"start": start_date, "end": end_date},
            "ads": ads,
            "total_spend_usd": sum(a["spend_usd"] for a in ads),
            "total_revenue_usd": sum(a["revenue_usd"] for a in ads),
            "blended_roas": (
                sum(a["revenue_usd"] for a in ads) / max(sum(a["spend_usd"] for a in ads), 0.01)
            ),
        }

    except Exception as e:
        return {"source": "meta_ads", "status": "error", "error": str(e), "ads": []}
