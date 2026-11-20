"""Bot — parses incoming messages, enforces basic rate limiting, and routes to tontine logic."""

from __future__ import annotations

import time
from collections import defaultdict, deque

import db
import tontine
from config import RATE_LIMIT_PER_MIN

# In-memory sliding-window rate limiter: phone_hash -> timestamps (per-process).
_hits: dict[str, deque[float]] = defaultdict(deque)


def _is_rate_limited(phone: str) -> bool:
    key = db.hash_phone(phone)
    now = time.time()
    window = 60.0
    q = _hits[key]
    cutoff = now - window
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        return True
    q.append(now)
    return False


async def handle_message(phone: str, text: str) -> str:
    """Parse a text message and return the response string."""
    text = (text or "").strip()
    if not text:
        return tontine.HELP_TEXT

    if _is_rate_limited(phone):
        return "Rate limit exceeded. Please wait a moment and try again."

    # Ensure user/wallet exists for non-greeting commands
    user = db.get_user(phone)
    if (not user or not user.get("wallet_id")) and not text.lower().split()[0] in {
        "hi",
        "hello",
        "start",
        "menu",
        "help",
        "h",
        "?",
    }:
        await tontine.register_user(phone)

    parts = text.lower().split()
    cmd = parts[0]
    args = parts[1:]

    match cmd:
        case "hi" | "hello" | "start":
            return await tontine.register_user(phone)

        case "menu" | "m":
            user = db.get_user(phone)
            bal_str = f" ({tontine.fmt(user['balance'])})" if user else ""
            return (
                f"📋 *WhatsApp Interactive Menu*{bal_str}\n\n"
                "Tap an interactive button below or reply with a number:\n\n"
                "1️⃣ *Check Balance* (`balance`)\n"
                "2️⃣ *Pay Contribution* (`pay`)\n"
                "3️⃣ *Group Status* (`status`)\n"
                "4️⃣ *Create Tontine* (`create`)\n"
                "5️⃣ *Join Tontine* (`join`)\n"
                "6️⃣ *Fund Wallet (+10k sats)* (`fund`)\n"
                "7️⃣ *Help & Commands* (`help`)"
            )

        case "1":
            return await tontine.handle_balance(phone)

        case "2":
            return await tontine.handle_pay(phone, args)

        case "3":
            return await tontine.handle_status(phone, args)

        case "4":
            return (
                "➕ *Create a Tontine Group*\n\n"
                "Format: `create <name> <amount_sats> <weekly|monthly> <members>`\n"
                "Example: `create Famille 2000 weekly 3`\n\n"
                "💡 Or click the *Create Tontine* button below to use the form!"
            )

        case "5":
            return (
                "👥 *Join a Tontine Group*\n\n"
                "Format: `join <tontine_id>`\n"
                "Example: `join 1`\n\n"
                "💡 Or click the *Join Group* button below!"
            )

        case "6":
            return await tontine.handle_fund(phone, ["10000"])

        case "7":
            return tontine.HELP_TEXT

        case "balance" | "bal" | "b":
            return await tontine.handle_balance(phone)

        case "create" | "new":
            return await tontine.handle_create(phone, args)

        case "join" | "j":
            return await tontine.handle_join(phone, args)

        case "pay" | "p":
            return await tontine.handle_pay(phone, args)

        case "status" | "s" | "info":
            return await tontine.handle_status(phone, args)

        case "fund" | "topup" | "add":
            return await tontine.handle_fund(phone, args)

        case "help" | "h" | "?":
            return tontine.HELP_TEXT

        case _:
            return f"Unknown command: '{cmd}'\n\n{tontine.HELP_TEXT}"
