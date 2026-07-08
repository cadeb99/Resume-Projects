# collectors/meta_ad_library.py — live Meta Ad Library API collector
import requests
from datetime import datetime
from config import META_AD_LIBRARY_TOKEN

SEARCH_TERMS = ["snowpants", "ski pants", "snowboard pants", "ski apparel", "powder pants"]


def get_data() -> dict:
    """Search Meta Ad Library for competitor activity in the snowsports apparel space."""
    try:
        all_ads = []
        for term in SEARCH_TERMS[:2]:  # Limit to avoid rate cap
            url = "https://graph.facebook.com/v19.0/ads_archive"
            params = {
                "access_token": META_AD_LIBRARY_TOKEN,
                "ad_type": "ALL",
                "ad_reached_countries": '["US","CA","AU","NZ","AT","JP","AR","CL"]',
                "search_terms": term,
                "fields": "id,page_name,ad_creation_time,ad_delivery_start_time,delivery_by_region",
                "limit": 50,
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            all_ads.extend(resp.json().get("data", []))

        competitors = {}
        for ad in all_ads:
            brand = ad.get("page_name", "Unknown")
            if brand not in competitors:
                competitors[brand] = {"brand": brand, "markets": [], "ads": [], "placements": []}
            competitors[brand]["ads"].append(ad)
            for region in ad.get("delivery_by_region", []):
                competitors[brand]["markets"].append(region.get("region", ""))

        result = []
        for brand, data in competitors.items():
            result.append({
                "brand": brand,
                "markets": list(set(data["markets"])),
                "placements": ["Feed"],
                "creative_longevity_days": len(data["ads"]),
                "long_running": len(data["ads"]) > 10,
            })

        return {
            "source": "meta_ad_library",
            "status": "ok",
            "retrieved_at": datetime.utcnow().isoformat(),
            "competitors": result,
            "total_competitors_found": len(result),
        }

    except Exception as e:
        return {"source": "meta_ad_library", "status": "error", "error": str(e), "competitors": []}
