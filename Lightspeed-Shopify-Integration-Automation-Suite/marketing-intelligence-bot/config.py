"""
Single place to flip demo -> live and configure store-specific context.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- THE SWITCH ---
# True  = mock Lightspeed inventory, randomized Meta ad data, no Gmail send (writes to file)
# False = real API calls everywhere (requires .env filled in)
DEMO_MODE = True

# --- Store context ---
# NOTE: the combined Stork & Bear Co. / Around the World Toys storefront is
# actually in Frisco, CO (610 Main St) — same Summit County market as Dillon,
# but the town name matters for local-event/weather accuracy. Confirmed via
# public listings (Yelp, town of Frisco business directory) as of 2026-07.
STORE_NAME = "Stork & Bear Co. / Around the World Toys"
STORE_ESTABLISHED_YEAR = 1986
STORE_LOCATION = {
    "city": "Frisco",
    "state": "CO",
    "county": "Summit County",
    "lat": 39.5744,
    "lon": -106.0973,
    "hemisphere": "northern",
}

# Product categories this bot understands (extend as Kathleen's catalog is finalized)
# Reflects the real product mix: Stork & Bear leans clothing/newborn, Around
# the World Toys leans wooden/educational toys, not mass-market plastic.
PRODUCT_CATEGORIES = [
    "winter_outerwear",       # Stork & Bear: snowsuits, jackets, mittens
    "everyday_clothing",      # Stork & Bear: onesies, basics, sizes newborn-tween
    "footwear",                # both stores
    "outdoor_toys",            # Around the World Toys: sleds, snow gear, bikes
    "educational_toys_games",   # Around the World Toys: wooden toys, puzzles, STEM/educational games
    "books_crafts",             # Around the World Toys: books, craft kits
    "plush_collectibles",       # Around the World Toys: stuffed animals, collectibles
    "gifts_novelty",            # both: local/Colorado-themed gifts, tourist gift buys
    "baby_gear",                # Stork & Bear: swaddles, nursing accessories
]

# Recipients for the weekly report
REPORT_RECIPIENTS = [
    os.getenv("REPORT_RECIPIENT_PRIMARY", "kathleen@example.com"),
]
REPORT_CC = []

# --- Credentials (all optional while DEMO_MODE = True) ---
LIGHTSPEED_API_KEY = os.getenv("LIGHTSPEED_API_KEY")
LIGHTSPEED_ACCOUNT_ID = os.getenv("LIGHTSPEED_ACCOUNT_ID")

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN")  # e.g. storkandbearco.myshopify.com
SHOPIFY_ADMIN_API_TOKEN = os.getenv("SHOPIFY_ADMIN_API_TOKEN")

GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS")

# --- Paths ---
DATA_DIR = "data"
LOG_DIR = "logs"
REPORT_OUTPUT_DIR = "reports/output"
MOCK_PRODUCTS_PATH = f"{DATA_DIR}/mock_products.json"
RUN_LOG_DB = f"{LOG_DIR}/run_history.sqlite"
