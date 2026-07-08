# config.py
# -----------------------------------------------
# MASTER CONTROL — flip this one line to go live
# -----------------------------------------------
DEMO_MODE = True  # Set to False when real APIs are ready

import os
from dotenv import load_dotenv

load_dotenv()

# Meta
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "")
META_AD_LIBRARY_TOKEN = os.getenv("META_AD_LIBRARY_TOKEN", "")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Gmail
GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT", "businessowner@gmail.com")
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/gmail_credentials.json")

# Scheduler
SCHEDULE_DAY = os.getenv("SCHEDULE_DAY", "sunday")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "08:00")

# Google Trends
GOOGLE_TRENDS_GEO = os.getenv("GOOGLE_TRENDS_GEO", "worldwide")
