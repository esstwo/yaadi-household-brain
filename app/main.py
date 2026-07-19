"""Yaadi FastAPI app — WhatsApp webhook, health check, reminder dispatch."""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Header, HTTPException, Response

load_dotenv()

from . import db
from .intent import parse_intent
from .router import handle

app = FastAPI(title="Yaadi")


@app.get("/health")
def health():
    """Hit by cron-job.org every ~10 min to keep the Render free instance warm."""
    return {"ok": True}


@app.post("/whatsapp")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    from twilio.twiml.messaging_response import MessagingResponse

    phone = From.replace("whatsapp:", "")
    user = db.get_user_by_phone(phone)

    if not user:
        reply = "I don't recognize this number yet. Ask Sumedh to add you to Yaadi."
    else:
        lists = [l["name"] for l in db.get_household_lists(user["household_id"])]
        now = datetime.now(timezone.utc).isoformat()
        intent = parse_intent(Body, lists, now)
        reply = handle(user, intent)

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")


@app.post("/dispatch")
def dispatch(x_dispatch_secret: str = Header(default="")):
    """Hit by cron-job.org every ~5 min. Sends any reminders now due."""
    if x_dispatch_secret != os.environ["DISPATCH_SECRET"]:
        raise HTTPException(403, "bad secret")

    from twilio.rest import Client

    twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    now = datetime.now(timezone.utc).isoformat()

    due = db.get_due_reminders(now)

    sent = 0
    for r in due:
        for phone in db.get_phones_for_reminder(r):
            # NOTE: outside the 24h window this must use an approved template.
            twilio.messages.create(
                from_=os.environ["TWILIO_WHATSAPP_FROM"],
                to=f"whatsapp:{phone}",
                body=f"Reminder: {r['text']}",
            )
        db.mark_reminder_sent(r["id"])
        sent += 1

    return {"dispatched": sent}
