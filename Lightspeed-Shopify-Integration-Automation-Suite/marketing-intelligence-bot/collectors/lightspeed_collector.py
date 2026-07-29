"""
Inventory source. In demo mode, reads the mock product file standing in for a
Lightspeed R-Series inventory export. In live mode, calls the Lightspeed R-Series
REST API (ir.merchantos.com) for current stock levels.

Swap-in point for live mode: replace `_fetch_live` with real API calls once
LIGHTSPEED_API_KEY / LIGHTSPEED_ACCOUNT_ID are available. Everything downstream
(scorer, content_generator) only depends on the dict shape returned here, so
that's the only function that needs to change.
"""
import json
import requests
import config


def get_inventory():
    if config.DEMO_MODE:
        return _fetch_mock()
    return _fetch_live()


def _fetch_mock():
    with open(config.MOCK_PRODUCTS_PATH) as f:
        return json.load(f)


def _fetch_live():
    """
    TODO once credentials exist: GET /Account/{accountID}/Item with
    Authorization header, paginate, map fields to the same shape as _fetch_mock.
    """
    raise NotImplementedError(
        "Live Lightspeed integration not yet wired. Set DEMO_MODE=True in "
        "config.py, or implement _fetch_live() with real API credentials."
    )
