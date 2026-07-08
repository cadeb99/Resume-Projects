# aggregator.py — combine all data sources into one unified dataset
import json
from datetime import datetime
from config import DEMO_MODE


def _load_source(source_name: str) -> dict:
    """Dynamically import the correct module based on DEMO_MODE."""
    try:
        if DEMO_MODE:
            mod = __import__(f"dummy.dummy_{source_name}", fromlist=["get_data"])
        else:
            mod = __import__(f"collectors.{source_name}", fromlist=["get_data"])
        return mod.get_data()
    except Exception as e:
        return {"source": source_name, "status": "error", "error": str(e)}


def aggregate() -> dict:
    """Pull all five sources and merge into a single dataset."""
    print(f"[aggregator] Running in {'DEMO' if DEMO_MODE else 'LIVE'} mode...")

    sources = ["meta_ads", "meta_ad_library", "google_trends", "open_meteo", "park_events"]
    results = {}
    errors = []

    for source in sources:
        print(f"  -> Collecting {source}...")
        data = _load_source(source)
        results[source] = data
        if data.get("status") == "error":
            errors.append(f"{source}: {data.get('error', 'unknown error')}")
            print(f"    [WARN] {source} failed: {data.get('error')}")
        else:
            print(f"    [OK] {source}")

    dataset = {
        "aggregated_at": datetime.utcnow().isoformat(),
        "demo_mode": DEMO_MODE,
        "sources": results,
        "source_errors": errors,
        "has_errors": len(errors) > 0,
    }

    return dataset


if __name__ == "__main__":
    data = aggregate()
    print(json.dumps(data, indent=2, default=str))
