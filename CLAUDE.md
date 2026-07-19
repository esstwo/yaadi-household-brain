# Yaadi — Project Guide for Claude Code

> यादी ("list" in Marathi/Hindi) — a shared household assistant that lives in WhatsApp.

## What this is

Both members of a household message a single WhatsApp number. An LLM parses each
message into a structured intent, then routes it to the right list, reminder, or
calendar event. Replies are short confirmations. No app to install, no UI to learn.

Example: "add eggs, milk to costco" → 2 items appended to the household's Costco
list → reply "Added 2 to Costco — 6 items total."

## Stack

| Layer | Choice | Notes |
|---|---|---|
| WhatsApp | Twilio | Sandbox for dev, paid number for prod |
| API | FastAPI | Single web service |
| Hosting | Render | Free tier, kept warm by external cron |
| Database | Supabase (Postgres) | Free tier |
| Intent parsing | Claude Haiku | Model string: `claude-haiku-4-5-20251001` |
| Scheduled jobs | cron-job.org | Pings `/dispatch` every 5 min (no paid Render cron) |
| Calendar | Google Calendar API | Per-user OAuth, refresh tokens in DB |

## Architecture

```
WhatsApp → Twilio → POST /whatsapp (FastAPI)
                         ↓
              look up sender phone → household
                         ↓
              parse_intent()  [Claude Haiku → structured JSON]
                         ↓
              route()  [add/list/remove/complete/schedule]
                         ↓
              Supabase read/write → reply via TwiML
```

Reminders run on a separate path: `cron-job.org` → `POST /dispatch` (shared-secret
auth) → query due reminders → send via Twilio API.

## Directory layout

```
yaadi/
├── CLAUDE.md          ← this file
├── README.md
├── PLAN.html          ← full project plan (open in browser)
├── requirements.txt
├── .env.example
├── schema.sql         ← paste into Supabase SQL editor
└── app/
    ├── __init__.py
    ├── main.py        ← FastAPI app, webhook + dispatch routes
    ├── intent.py      ← Claude intent parser (returns structured dict)
    ├── router.py      ← maps intent → Supabase actions
    └── db.py          ← Supabase client + helpers
```

## Conventions

- **Intent is always structured JSON.** `intent.py` prompts Claude to return ONLY
  JSON matching a fixed schema (action, list_name, items, when, scope, reply).
  Strip code fences before `json.loads`. Never regex-parse user messages.
- **Claude generates the reply text** inside the same intent call — keeps tone
  consistent and avoids a second round-trip.
- **Lists belong to households, not users.** Identity comes free from the inbound
  phone number; look up `users.phone` → `household_id` → scope all queries to it.
- **Phone numbers are E.164** (`+15105551234`). Twilio sends `whatsapp:+1510...`;
  strip the `whatsapp:` prefix before DB lookup.
- **Use Haiku, not Sonnet** for intent parsing — it's plenty and ~10x cheaper.

## Non-obvious gotchas (don't skip these)

1. **WhatsApp 24-hour rule.** You can reply freely within 24h of a user's last
   inbound message. Outbound messages outside that window (e.g. a 6am reminder)
   REQUIRE a pre-approved message template. Reminders in Phase 2 need this.
2. **Render free tier sleeps after 15 min.** Twilio's webhook times out at ~15s,
   but cold start takes 30–60s → first message after idle can fail and retry
   (duplicate replies). Fix: external cron pings `/health` every 10 min to keep warm.
3. **Verify Twilio signatures** on `/whatsapp` in production — otherwise anyone
   with the URL can spam the webhook. Use `twilio.request_validator`.
4. **`/dispatch` needs its own auth.** It's a public endpoint hit by cron-job.org;
   protect it with a shared secret in a header, checked before doing anything.

## Build phases

- [ ] **Phase 1** — Echo → shared grocery list (Twilio sandbox, schema, intent, add/list/remove)
- [ ] **Phase 2** — Scheduled reminders (reminders table, /dispatch, cron, template)
- [ ] **Phase 3** — Google Calendar (OAuth, token storage, schedule_event intent)
- [ ] **Phase 4** — Optional: voice notes, photo→ingredients, web dashboard, Meta Cloud API

Current status: **Phase 1, not started.** Build the echo loop first, then schema, then intent.

## Commands

```bash
# Local dev
uvicorn app.main:app --reload --port 8000
ngrok http 8000                 # paste URL into Twilio sandbox webhook

# Deploy: push to main, Render auto-deploys
# Start command on Render:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## What to do when starting fresh

If asked to "start building," begin with Phase 1: get `POST /whatsapp` echoing
messages back, then add the Supabase schema, then wire `intent.py`. Don't build
Phase 2/3 code until Phase 1 works end-to-end on a real phone.
