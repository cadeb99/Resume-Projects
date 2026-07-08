# Instagram DM Automation

A proof-of-concept tool that auto-replies to Instagram DMs with an AI trained on
a business's product info — and knows when to hand a conversation to a human.

Built with **Python + FastAPI + Claude**. Small, readable code; one module per job.

---

## How it works

```
Customer DM
    │
    ▼
Meta sends a webhook ──▶  POST /webhook   (verifies it's really from Meta, replies 200 fast)
                              │
                              ▼  (background)
                     ┌─────────────────────┐
                     │  1. Log the message  │  database.py   (Req 6)
                     │  2. Ask Claude       │  ai.py         (Req 3)
                     │  3. Human takeover?  │  takeover.py   (Req 5)
                     │  4. Send the reply   │  instagram.py  (Req 4)
                     └─────────────────────┘
                              │
              ┌───────────────┴───────────────┐
        send via Graph API              alert the owner
        (3 retries, Req 4)              (console/Slack/SMS, Req 5 & 7)
```

## Where each requirement lives

| # | Requirement | Implemented in |
|---|-------------|----------------|
| 1 | Meta setup + backup app | [config.py](app/config.py) (`ACTIVE_APP` switch) + this README |
| 2 | 24/7 server, fast ack, handles load | [main.py](app/main.py) (background tasks, `/webhook`) |
| 3 | AI replies + "we'll get back to you" fallback | [ai.py](app/ai.py) |
| 4 | Send reply, retry 3×, then alert | [instagram.py](app/instagram.py) + [main.py](app/main.py) |
| 5 | Human takeover on refunds/complaints/low confidence | [takeover.py](app/takeover.py) + [notifier.py](app/notifier.py) |
| 6 | Log every message, reply, and error | [database.py](app/database.py) |
| 7 | Cloud hosting + uptime monitoring + 2 instances | [Dockerfile](Dockerfile), [render.yaml](render.yaml), `/health` |

---

## Quick start (run it locally in 5 minutes)

```powershell
# 1. Copy the env template and add your Anthropic API key
Copy-Item .env.example .env
#    then open .env and paste your ANTHROPIC_API_KEY

# 2. Install and run (creates a virtual environment for you)
.\run_local.ps1
```

The server starts at `http://localhost:8000`. Check it's alive:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### Demo without Instagram (use this in the meeting)

Your Meta app may take days to get approved, so there's a `/simulate` endpoint
that runs a fake DM through the **entire** AI + takeover pipeline — no Instagram
needed:

```powershell
# A normal question -> AI answers
Invoke-RestMethod -Method Post http://localhost:8000/simulate `
  -ContentType "application/json" `
  -Body '{"text": "Do you ship to Texas? How much?"}'

# A refund -> bot pauses and flags a human
Invoke-RestMethod -Method Post http://localhost:8000/simulate `
  -ContentType "application/json" `
  -Body '{"text": "I want a refund, this arrived broken"}'
```

You'll see the AI's reply, its confidence score, and whether a human takeover
was triggered. Everything is also saved to the database (`data/automation.db`).

### Run the tests

```powershell
pytest
```

---

## Connecting real Instagram (Requirement 1)

This uses Meta's **official** Instagram Messaging API — the sanctioned way for a
business to auto-reply to its own DMs.

1. Create a Meta app at [developers.facebook.com](https://developers.facebook.com/) → **Create App** → "Business".
2. Add the **Instagram** product and connect the business's Instagram (must be a
   Professional/Business account linked to a Facebook Page).
3. Request the messaging permissions (`instagram_manage_messages`). This needs
   Meta App Review — start it early.
4. Copy into `.env`:
   - `IG_APP_SECRET` — App Settings → Basic → App Secret
   - `IG_ACCESS_TOKEN` — the Page/Instagram access token
   - `IG_VERIFY_TOKEN` — any random string (you'll paste the same one into Meta)
5. Set up the webhook: point it at `https://your-domain/webhook`, use your
   `IG_VERIFY_TOKEN`, and subscribe to the `messages` field.

### Backup app (Requirement 1)

If Meta revokes or limits the primary app, create a second Meta app, put its
credentials in `IG_BACKUP_APP_SECRET` / `IG_BACKUP_ACCESS_TOKEN`, and set
`ACTIVE_APP=backup`. No code change — just restart.

---

## Hosting it for real (Requirement 7)

The included [render.yaml](render.yaml) deploys to [Render](https://render.com)
with a Docker container, automatic restarts, a `/health` check, and **2 instances**
so one crash doesn't take the bot down. (Railway, Fly.io, AWS, etc. work too —
the `Dockerfile` is standard.)

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, point it at your repo.
3. Add your secrets (`ANTHROPIC_API_KEY`, `IG_*`) in the dashboard.

### Uptime monitoring + 2am text alert

- Sign up for [UptimeRobot](https://uptimerobot.com) (free) and add an HTTP
  monitor for `https://your-domain/health`. It texts/emails you if the site goes down.
- For in-app alerts (human takeover, failed sends), set `NOTIFY_CHANNEL` in `.env`:
  - `slack` + `SLACK_WEBHOOK_URL` → posts to a Slack channel
  - `twilio` + Twilio creds → **sends an SMS to your friend's phone**

---

## What's a real POC vs. production-ready

**Working now:** the full pipeline — webhook, AI replies with fallback, retries,
human takeover, logging, health check, Docker deploy, and a demo endpoint.

**Hardening for production later:**
- Swap SQLite → PostgreSQL (change `database.py`; tables stay the same).
- True autoscaling under heavy load (raise `numInstances` / move to a queue).
- For high message volume, switch `AI_MODEL` to `claude-haiku-4-5` for lower
  latency and cost.

---

## Project layout

```
app/
  config.py         settings + backup-app switch
  main.py           FastAPI server + the message pipeline
  ai.py             Claude reply generation + latency fallback
  instagram.py      send DMs (with retry) + verify webhooks
  takeover.py       human-takeover detection
  notifier.py       owner alerts (console / Slack / SMS)
  database.py       SQLite logging
  knowledge_base.py loads data/product_info.md
data/
  product_info.md   <-- edit this with the real business details
tests/              fallback + takeover tests
Dockerfile, render.yaml   deployment
```
