"""Route a parsed intent to the right DB action, return reply text."""
from . import db


def handle(user: dict, intent: dict) -> str:
    household_id = user["household_id"]
    action = intent.get("action")

    if action == "add":
        lst = db.get_list(household_id, intent["list_name"])
        if not lst:
            return (
                f"There's no '{intent['list_name']}' list yet. "
                f"Reply 'create {intent['list_name']}' and I'll start one."
            )
        db.insert_items(lst["id"], user["id"], intent["items"])
        return intent["reply"]

    if action == "list":
        lst = db.get_list(household_id, intent["list_name"])
        if not lst:
            return f"No '{intent['list_name']}' list yet."
        items = db.get_open_items(lst["id"])
        if not items:
            return f"{intent['list_name'].title()} is empty."
        body = "\n".join(f"• {i['text']}" for i in items)
        return f"{intent['list_name'].title()} ({len(items)}):\n{body}"

    if action == "schedule":
        db.insert_reminder(
            household_id=household_id,
            created_by=user["id"],
            text=intent["items"][0] if intent["items"] else intent["reply"],
            remind_at=intent["when"],
            scope=intent.get("scope") or "me",
        )
        return intent["reply"]

    # complete / remove: TODO — fuzzy match items by text, mark done or delete
    # clarify / fallback:
    return intent["reply"]
