"""
Online sales/engagement per SKU from Shopify. In demo mode, reads the mock
order/session file standing in for a Shopify Admin API export. In live mode,
calls the Shopify Admin API (Orders + Analytics) once SHOPIFY_* credentials
exist in .env / config.py.

Swap-in point for live mode: replace `_fetch_live` with real API calls.
Downstream code only depends on the dict shape returned here.
"""
import json
import config

MOCK_SHOPIFY_PATH = f"{config.DATA_DIR}/mock_shopify_orders.json"


def get_online_performance():
    """Returns {sku: {sessions_30d, add_to_cart_30d, units_sold_online_30d,
    traffic_source_top, conversion_rate_pct}}."""
    if config.DEMO_MODE:
        return _fetch_mock()
    return _fetch_live()


def _fetch_mock():
    with open(MOCK_SHOPIFY_PATH) as f:
        raw = json.load(f)
    for sku, stats in raw.items():
        sessions = stats.get("sessions_30d", 0)
        sold = stats.get("units_sold_online_30d", 0)
        stats["conversion_rate_pct"] = round((sold / sessions) * 100, 2) if sessions else 0.0
    return raw


def _fetch_live():
    """
    TODO once credentials exist: pull Orders (line items by SKU) and
    Shopify Analytics (sessions, add-to-cart events) for the trailing 30
    days via Shopify Admin API / GraphQL, map to the same shape as
    _fetch_mock.
    """
    raise NotImplementedError(
        "Live Shopify integration not yet wired. Set DEMO_MODE=True in "
        "config.py, or implement _fetch_live() with real API credentials."
    )
