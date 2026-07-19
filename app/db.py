"""Postgres (Neon) client and query helpers.

All access goes through helpers here so callers never touch raw SQL.
"""
import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    os.environ["DATABASE_URL"],
    min_size=1,
    max_size=5,
    kwargs={"row_factory": dict_row},
    # Neon free-tier auto-suspends after ~5 min idle and kills pooled connections.
    # check runs a lightweight ping on each checkout and reconnects if dead.
    check=ConnectionPool.check_connection,
    open=True,
)


@contextmanager
def conn():
    with pool.connection() as c:
        yield c


# ── users / lists ──────────────────────────────────────────────────────────

def get_user_by_phone(phone: str) -> dict | None:
    """phone is E.164 without the 'whatsapp:' prefix.
    Result includes last_list_name (may be None) from a join on lists."""
    with conn() as c:
        return c.execute(
            "select u.*, l.name as last_list_name"
            " from users u left join lists l on l.id = u.last_list_id"
            " where u.phone = %s",
            (phone,),
        ).fetchone()


def set_user_last_list(user_id, list_id) -> None:
    with conn() as c:
        c.execute(
            "update users set last_list_id = %s where id = %s", (list_id, user_id)
        )


def get_household_lists(household_id) -> list[dict]:
    with conn() as c:
        return c.execute(
            "select * from lists where household_id = %s", (household_id,)
        ).fetchall()


def get_list(household_id, name: str) -> dict | None:
    with conn() as c:
        return c.execute(
            "select * from lists where household_id = %s and name = %s",
            (household_id, name),
        ).fetchone()


# ── items ──────────────────────────────────────────────────────────────────

def insert_items(list_id, added_by, items: list[str]) -> None:
    with conn() as c, c.cursor() as cur:
        cur.executemany(
            "insert into items (list_id, text, added_by) values (%s, %s, %s)",
            [(list_id, t, added_by) for t in items],
        )


def get_open_items(list_id) -> list[dict]:
    with conn() as c:
        return c.execute(
            "select text from items where list_id = %s and done = false", (list_id,)
        ).fetchall()


def find_open_items_by_search(list_id, terms: list[str]) -> list[dict]:
    """Case-insensitive substring match — one row per (item × term hit)
    is fine since we dedupe by id downstream."""
    if not terms:
        return []
    with conn() as c:
        conditions = " OR ".join(["text ilike %s"] * len(terms))
        params = [list_id, *(f"%{t}%" for t in terms)]
        return c.execute(
            f"select distinct id, text from items"
            f" where list_id = %s and done = false and ({conditions})",
            params,
        ).fetchall()


def mark_items_done(item_ids: list) -> None:
    if not item_ids:
        return
    with conn() as c:
        c.execute("update items set done = true where id = any(%s)", (item_ids,))


def delete_items(item_ids: list) -> None:
    if not item_ids:
        return
    with conn() as c:
        c.execute("delete from items where id = any(%s)", (item_ids,))


def clear_list(list_id) -> int:
    """Delete all open items from a list. Returns rows removed."""
    with conn() as c:
        res = c.execute(
            "delete from items where list_id = %s and done = false", (list_id,)
        )
        return res.rowcount


# ── reminders ──────────────────────────────────────────────────────────────

def insert_reminder(household_id, created_by, text: str, remind_at, scope: str) -> None:
    with conn() as c:
        c.execute(
            "insert into reminders (household_id, created_by, text, remind_at, scope)"
            " values (%s, %s, %s, %s, %s)",
            (household_id, created_by, text, remind_at, scope),
        )


def get_due_reminders(now_iso: str) -> list[dict]:
    with conn() as c:
        return c.execute(
            "select * from reminders where remind_at <= %s and sent = false",
            (now_iso,),
        ).fetchall()


def mark_reminder_sent(reminder_id) -> None:
    with conn() as c:
        c.execute("update reminders set sent = true where id = %s", (reminder_id,))


def get_phones_for_reminder(reminder: dict) -> list[str]:
    with conn() as c:
        if reminder["scope"] == "me":
            row = c.execute(
                "select phone from users where id = %s", (reminder["created_by"],)
            ).fetchone()
            return [row["phone"]] if row else []
        rows = c.execute(
            "select phone from users where household_id = %s",
            (reminder["household_id"],),
        ).fetchall()
        return [r["phone"] for r in rows]
