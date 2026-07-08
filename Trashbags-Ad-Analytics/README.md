# Baggy Snowpants — Weekly Ad Performance Automation

Pulls live Instagram/Facebook ad data, cross-references ski market conditions,
analyzes everything with Claude, and delivers a formatted HTML report to your inbox every Sunday.

Runs in **DEMO MODE by default** — no API credentials needed to test the full pipeline.

---

## Quick Start (Demo Mode — no credentials needed)

```bash
# 1. Clone / download the project
cd "project folder"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the env example (no changes needed for demo)
cp .env.example .env

# 4. Add your Anthropic API key to .env
#    ANTHROPIC_API_KEY=sk-ant-...
#    (Only key required for demo — everything else uses fake data)

# 5. Run the pipeline once
python scheduler.py --now
```

The report saves to **`demo_email_output.html`** in the project root.
Open it in any browser to preview the full formatted email.

---

## Project Structure

```
project/
├── collectors/          # Live API collectors (used when DEMO_MODE=false)
│   ├── meta_ads.py
│   ├── meta_ad_library.py
│   ├── google_trends.py
│   ├── opensnow.py
│   └── weather.py
├── dummy/               # Fake data generators (used when DEMO_MODE=true)
│   ├── dummy_meta_ads.py
│   ├── dummy_meta_ad_library.py
│   ├── dummy_google_trends.py
│   ├── dummy_opensnow.py
│   └── dummy_weather.py
├── aggregator.py        # Combines all five sources into one payload
├── analyzer.py          # Sends payload to Claude API, returns HTML
├── emailer.py           # Saves HTML (demo) or sends via Gmail (live)
├── ski_calendar.py      # Global market registry + hemisphere season logic
├── scheduler.py         # Weekly schedule runner + manual --now flag
├── config.py            # Single source of truth for all settings
├── .env.example         # All credentials documented with instructions
├── requirements.txt
└── README.md
```

---

## Switching from Demo to Live

**One line change in `config.py`:**

```python
# config.py
DEMO_MODE = False   # was True
```

Or set in your `.env` file:

```
DEMO_MODE=false
```

Then fill in each credential in `.env` following the instructions below.

---

## Credential Setup (Live Mode)

### 1. Anthropic API (required for both modes)
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Create an API key
3. Set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`

### 2. Meta Marketing API
1. Go to [developers.facebook.com](https://developers.facebook.com) and create an app
2. Add the **Marketing API** product
3. Generate a User Access Token with `ads_read` scope
4. Find your Ad Account ID in Business Manager → Ad Accounts
5. Set `META_ACCESS_TOKEN` and `META_AD_ACCOUNT_ID` in `.env`

### 3. Meta Ad Library API
1. Visit [facebook.com/ads/library/api](https://www.facebook.com/ads/library/api)
2. Register your developer app for Ad Library access
3. Set `META_AD_LIBRARY_TOKEN` in `.env`

### 4. Google Trends
No key required — uses the [pytrends](https://github.com/GeneralMills/pytrends) library.

### 5. OpenSnow API
Contact [OpenSnow](https://opensnow.com/api) directly for API access.
Set `OPENSNOW_API_KEY` in `.env`.

### 6. Weather API (Tomorrow.io)
1. Sign up at [tomorrow.io](https://www.tomorrow.io/weather-api) (free tier available)
2. Copy your API key from the dashboard
3. Set `WEATHER_API_KEY` in `.env`

### 7. Gmail API
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable the Gmail API
3. Create **OAuth2 credentials** (Desktop app type)
4. Download the JSON and save as `credentials/gmail_credentials.json`
5. First run will open a browser for OAuth consent — token is saved automatically after
6. Set `GMAIL_RECIPIENT` to the destination email in `.env`

---

## Running the Pipeline

### Run once (manual test)
```bash
python scheduler.py --now
```

### Start the weekly scheduler
```bash
python scheduler.py
```
Runs every Sunday at 08:00 by default. Change `SCHEDULE_DAY` and `SCHEDULE_TIME` in `.env`.

### Run individual components
```python
# Test aggregation only
python -c "import aggregator; import json; print(json.dumps(aggregator.run(), indent=2, default=str))"

# Test aggregation + analysis (outputs to console)
python -c "import aggregator, analyzer; d=aggregator.run(); print(analyzer.run(d))"
```

---

## Logs

Every pipeline run logs to `logs/run_YYYY-MM-DD.log`.
If any data source fails, the error is noted in the log and included in the email — the pipeline continues with remaining sources.

---

## Scheduler Configuration

| Variable | Default | Description |
|---|---|---|
| `SCHEDULE_DAY` | `sunday` | Day of week to send report |
| `SCHEDULE_TIME` | `08:00` | Time to send (24h, local machine time) |

---

## Requirements

- Python 3.10+
- Internet connection (for Claude API, even in demo mode)
- All packages listed in `requirements.txt`

---

## Data Sources

| Source | Purpose | Read/Write |
|---|---|---|
| Meta Marketing API | Your ad performance — impressions, CTR, CPC, ROAS, placements, geos | Read only |
| Meta Ad Library API | Competitor ads currently running | Read only |
| Google Trends (pytrends) | Search volume spikes by region | Read only |
| OpenSnow API | Resort conditions, traffic, new openings | Read only |
| Tomorrow.io Weather API | 7-day snowfall forecasts by region | Read only |
| Claude API (Anthropic) | Analysis and recommendation generation | Write (API calls) |
| Gmail API | Weekly report delivery | Write (send email) |

**No write access to Meta. No real money is moved by this system.**
