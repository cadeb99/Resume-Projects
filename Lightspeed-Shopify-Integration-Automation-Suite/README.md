---
## Lightspeed R-Series to Shopify E-Commerce Integration & Automation Suite

**Role:** Project Lead & Integration Architect
**Client:** Stork & Bear / Around the World Toys, Dillon, CO
**Status:** In progress, targeting August/September 2026 launch

This project bridges a Lightspeed R-Series POS system with Shopify for two independent retail stores, combining a real-time bidirectional inventory sync with a full Python automation suite hosted on GCP Cloud Run.

**What this covers:**
- Bidirectional Lightspeed <-> Shopify inventory sync (~70 SKUs)
- Automated sales tax reporting, low-inventory alerts, and revenue reporting
- A marketing ad-intelligence system cross-referencing live inventory (Lightspeed API), Google Trends (pytrends), seasonal weather (Open-Meteo), and Meta ad performance to surface ranked product advertising recommendations
- Meta Commerce Manager integration connecting the Shopify catalog to Facebook/Instagram ads
- Full local SEO strategy and technical launch checklist

**My role:** I scoped the full system, architected the integration and automation pipeline, managed client communication and documentation (5 client-facing guides), and led a two-person dev team through implementation. This system reuses and extends an ad-intelligence architecture I already built and run in production for a separate client, adapted here for e-commerce and retail inventory data.

**Stack:** Python, Lightspeed R-Series REST API, Shopify Admin REST API, Meta Graph API (Marketing + Ad Library), pytrends, Open-Meteo API, Gmail API, UPS API, GCP (Cloud Run, Cloud Scheduler, Cloud Storage), Docker, SQLite, OAuth2
---

### A note on this repo

> **The tax reporting system shown/described below is still running in demo mode.**
> It's built and tested against randomized fake order data, not the client's real
> sales figures. Live credentials (Shopify, Lightspeed, Zoho email, Google Sheets)
> are intentionally withheld from this public repo to protect the client's private
> business data. Code structure, logic, and automation design shown here are real
> and production-ready — only the data flowing through it is simulated.

### Closed-loop sales tax reporting (build detail)

One completed piece of the broader automation suite: a fully automated, self-verifying
sales tax reporting pipeline for the two stores.

**Daily report**
- Pulls the day's orders from both Shopify (online) and Lightspeed (in-store) and
  reconciles them against each other.
- Breaks tax collected down by store, by channel (in-store vs. online), and by
  Colorado (in-state) vs. out-of-state — including a per-state destination
  breakdown for out-of-state shipments, for filing reference.
- A verification layer independently recalculates the expected tax on every
  single order and cross-checks that every grouping (store/channel/state) sums
  back to the same grand total, flagging any discrepancy before it ever reaches
  the client — nothing is reported on faith.
- Delivered as a responsive HTML email report (readable on both desktop and
  mobile) with a plain-language summary for a non-technical reader.

**Monthly spreadsheet rotation**
- A new Google Sheet is created automatically for each calendar month, so no
  single spreadsheet ever grows unmanageable.
- Past months are never touched or deleted — they remain in a shared Drive
  folder as a permanent, browsable archive the client can reference at any time.

**Yearly filing report**
- Runs automatically one month before the business's tax filing deadline.
- Aggregates all twelve of the prior year's monthly spreadsheets into one
  combined summary, re-verifies the totals, and links back to each month's
  detail — a single document ready to hand to an accountant.

**Delivery**
- Emailed via Zoho Mail SMTP from the business's automated-services mailbox.
- Every run (success or failure) is logged with a timestamp; failures exit
  with a non-zero status so a scheduled run failure is never silent.

**Engineering notes**
- Demo mode and live mode share the exact same code path — the system detects
  whether live Shopify/Lightspeed credentials are present and switches
  automatically, with no manual flag to remember. Email and Sheets delivery
  each independently fall back to writing locally until their own credentials
  are configured, so partial setup never breaks the rest of the pipeline.
- Designed to deploy as two scheduled GCP Cloud Run Jobs (daily + yearly),
  triggered by Cloud Scheduler, fully documented in the project's own
  `DEPLOY.md` for a clean handoff to the client with no day-to-day engineering
  attention required.
