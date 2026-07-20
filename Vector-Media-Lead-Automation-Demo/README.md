[README.md](https://github.com/user-attachments/files/30199633/README.md)
# Lead Follow-Up Automation - Proof of Concept

A small proof-of-concept built after applying for the Tech Specialist role at Vector Media,
inspired by the posting's call for someone who identifies manual workflows and automates them
with tools like Zapier.

## What it does

Simulates the flow of a new inbound lead (sales inquiry, partnership request, experiential
booking, support issue, etc.) and automatically:

1. **Classifies** the lead by keyword matching (sales / partnership / experiential / support / general)
2. **Routes** it to the correct team
3. **Logs** it to a shared tracker (a CSV here, standing in for a Google Sheet, Airtable, or CRM)
4. **Notifies** the right owner (printed here, standing in for a Slack message or email)

## Why it's built this way

The classify -> log -> notify pipeline doesn't change whether the input is a mock message
or a real webhook from a website form, and whether the output is a printed line or a real
Slack/Zapier webhook call. That's the point: the core logic is reusable regardless of which
real tools sit on either end.

## Run it

```bash
python3 lead_router.py
```

Outputs a run to the console and writes `lead_log.csv` alongside the script.

## Next steps to make this production-ready

- Swap `MOCK_LEADS` for a real source (a webhook from a website form, or polling a Gmail inbox)
- Swap `notify_owner()`'s print statement for a real Slack webhook or Zapier trigger
- Swap the CSV log for a real Google Sheet (via API) or CRM entry
- Add confidence scoring / fallback to a human for ambiguous leads that don't clearly match a category
