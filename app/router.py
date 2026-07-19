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
        db.set_user_last_list(user["id"], lst["id"])
        return intent["reply"]

    if action == "list":
        lst = db.get_list(household_id, intent["list_name"])
        if not lst:
            return f"No '{intent['list_name']}' list yet."
        db.set_user_last_list(user["id"], lst["id"])
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

    if action in ("remove", "complete"):
        lst = db.get_list(household_id, intent["list_name"])
        if not lst:
            return f"No '{intent['list_name']}' list yet."
        db.set_user_last_list(user["id"], lst["id"])
        matches = db.find_open_items_by_search(lst["id"], intent["items"])
        if not matches:
            wanted = ", ".join(intent["items"]) or "anything"
            return f"Couldn't find {wanted} on {intent['list_name']}."
        ids = [m["id"] for m in matches]
        texts = [m["text"] for m in matches]
        if action == "complete":
            db.mark_items_done(ids)
            verb = "Completed"
        else:
            db.delete_items(ids)
            verb = "Removed"
        return f"{verb} {len(matches)} from {intent['list_name']}: {', '.join(texts)}."

    if action == "clear":
        lst = db.get_list(household_id, intent["list_name"])
        if not lst:
            return f"No '{intent['list_name']}' list yet."
        db.set_user_last_list(user["id"], lst["id"])
        removed = db.clear_list(lst["id"])
        if removed == 0:
            return f"{intent['list_name'].title()} was already empty."
        return f"Cleared {intent['list_name']} — removed {removed} item{'s' if removed != 1 else ''}."

    # clarify / fallback:
    return intent["reply"]
