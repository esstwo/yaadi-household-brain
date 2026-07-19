"""Yaadi FastAPI app — WhatsApp webhook, health check, reminder dispatch."""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, Response

load_dotenv()

from . import db
from .intent import parse_intent
from .router import handle

app = FastAPI(title="Yaadi")

VALIDATE_SIGNATURE = os.environ.get("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true"


@app.get("/health")
def health():
    """Hit by cron-job.org every ~10 min to keep the Render free instance warm."""
    return {"ok": True}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    from twilio.request_validator import RequestValidator
    from twilio.twiml.messaging_response import MessagingResponse

    form = await request.form()

    if VALIDATE_SIGNATURE:
        # Rebuild the URL Twilio signed. Behind ngrok / Render's proxy, request.url
        # shows the internal scheme+host; the forwarded headers hold the public one.
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        url = f"{proto}://{host}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"
        validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
        signature = request.headers.get("x-twilio-signature", "")
        if not validator.validate(url, dict(form), signature):
            raise HTTPException(403, "invalid twilio signature")

    phone = form.get("From", "").replace("whatsapp:", "")
    user = db.get_user_by_phone(phone)

    if not user:
        reply = "I don't recognize this number yet. Ask Sumedh to add you to Yaadi."
    else:
        lists = [l["name"] for l in db.get_household_lists(user["household_id"])]
        now = datetime.now(timezone.utc).isoformat()
        intent = parse_intent(
            form.get("Body", ""), lists, now, last_list=user.get("last_list_name")
        )
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
