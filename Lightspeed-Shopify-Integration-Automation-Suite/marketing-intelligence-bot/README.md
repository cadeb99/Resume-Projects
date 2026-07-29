# Stork & Bear / Around the World Toys — Marketing Intelligence Bot

Weekly automated system that tells Kathleen **what to advertise, why, and what to post** —
built from in-stock inventory, Google Trends, seasonal/local context (Dillon, CO ski town),
and Meta ad performance.

This is module 1 of the larger Stork & Bear / Around the World Toys automation project
(inventory alerts, sales tax report, revenue report are separate modules, not built yet).

## Status: ROUGH DRAFT — DEMO MODE ONLY

No live API credentials are wired in. Everything runs on:
- Mock product list (`data/mock_products.json`) standing in for Lightspeed inventory
- Real Google Trends calls (pytrends, no auth needed) OR randomized fallback if it fails
- Real Open-Meteo weather calls (no auth needed) for Dillon, CO
- Randomized dummy Meta ad performance data

Flip `DEMO_MODE = False` in `config.py` once real Lightspeed/Meta/Gmail credentials exist.
Nothing else in the code should need to change — collectors already check the flag.

## Why this shape

Kathleen runs two stores (kids clothing + toys) in a ski/tourist town. The bot's whole job
is cross-referencing three things every week:
1. **What's actually in stock** (no point advertising something sold out)
2. **What's trending** (Google search interest by product category)
3. **What's seasonally/locally relevant** (ski season influx vs. summer tourist season vs. birthdays/holidays year-round)

...into a ranked "advertise this" list, plus ready-to-use social post ideas and ad copy
variants for the top picks. Delivered as one HTML email.

## Structure

```
config.py                      # DEMO_MODE switch + store/location config
data/mock_products.json        # stand-in for Lightspeed inventory export
collectors/
  lightspeed_collector.py      # inventory (mock in demo mode)
  trends_collector.py          # Google Trends via pytrends
  weather_collector.py         # Open-Meteo, Dillon CO coords
  meta_collector.py            # ad performance (mock in demo mode)
  seasonal_context.py          # ski season / tourist calendar / holiday logic
analysis/
  scorer.py                    # ranks products -> "advertise more" list
  content_generator.py         # social post ideas + ad copy variants
reports/
  report_generator.py          # builds the HTML report
  gmail_sender.py               # sends it (demo mode: writes to file instead)
aggregator.py                  # wires the pipeline together
main.py                        # entry point
requirements.txt
.env.example
run_report.sh
```

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

In demo mode this writes the report to `reports/output/latest_report.html` and prints a
summary to the console instead of emailing (no Gmail credentials required to test).

## Handoff notes for whoever picks this up

- This folder is meant to be zipped/copied whole and handed to the store owner or next dev.
- `.env.example` documents every credential this will eventually need — copy to `.env` and
  fill in when Lightspeed/Meta/Gmail access exists.
- `config.py` is the only file that should need editing to go from demo -> live.
- Product categories, seasonal windows, and copy templates are all guesses based on the
  project brief — Kathleen should review and correct `data/mock_products.json` and
  `collectors/seasonal_context.py` once real inventory/calendar info is available.
