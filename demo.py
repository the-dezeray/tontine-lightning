"""One-command reproducible demo for Tontine Lightning.

Runs the full happy path on an isolated fresh SQLite database (mock mode).
Verifies expected outcomes and exits 0 on success, 1 on failure.

Usage:
    python demo.py
"""

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

# Configure isolated demo DB BEFORE importing app modules (config/db init on import).
DEMO_DB = Path(tempfile.gettempdir()) / "tontine_lightning_demo.db"
if DEMO_DB.exists():
    DEMO_DB.unlink()
os.environ["DATABASE"] = str(DEMO_DB)
os.environ.setdefault("MOCK_MODE", "true")

# Ensure local imports resolve when run from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot  # noqa: E402
import db  # noqa: E402


def _extract_tontine_id(text: str) -> int:
    m = re.search(r"\(ID:\s*(\d+)\)", text)
    if not m:
        raise AssertionError(f"Could not parse tontine ID from: {text!r}")
    return int(m.group(1))


async def run() -> None:
    p1, p2, p3 = "+221771111111", "+221772222222", "+221773333333"
    steps: list[tuple[str, str]] = []

    def log(label: str, msg: str) -> str:
        steps.append((label, msg))
        print(f"\n=== {label} ===")
        print(msg)
        return msg

    # Register and fund
    log("User 1 registers", await bot.handle_message(p1, "hi"))
    log("User 1 funds", await bot.handle_message(p1, "fund 10000"))
    create_msg = log("User 1 creates tontine", await bot.handle_message(p1, "create Famille 2000 weekly 3"))
    tid = _extract_tontine_id(create_msg)
    print(f"[demo] tontine_id={tid}")

    log("User 2 registers", await bot.handle_message(p2, "hi"))
    log("User 2 funds", await bot.handle_message(p2, "fund 10000"))
    log("User 2 joins", await bot.handle_message(p2, f"join {tid}"))

    log("User 3 registers", await bot.handle_message(p3, "hi"))
    log("User 3 funds", await bot.handle_message(p3, "fund 10000"))
    log("User 3 joins", await bot.handle_message(p3, f"join {tid}"))

    log("Status before payments", await bot.handle_message(p1, f"status {tid}"))

    pay1 = log("User 1 pays", await bot.handle_message(p1, f"pay {tid}"))
    pay2 = log("User 2 pays", await bot.handle_message(p2, f"pay {tid}"))
    pay3 = log("User 3 pays (triggers payout)", await bot.handle_message(p3, f"pay {tid}"))

    bal1 = log("User 1 balance", await bot.handle_message(p1, "balance"))
    bal2 = log("User 2 balance", await bot.handle_message(p2, "balance"))
    bal3 = log("User 3 balance", await bot.handle_message(p3, "balance"))
    status_after = log("Status after payout", await bot.handle_message(p1, f"status {tid}"))

    # Assertions
    errors: list[str] = []

    if "ALL PAID" not in pay3 and "Pot of" not in pay3 and "payout" not in pay3.lower():
        errors.append("Expected payout to trigger on final payment.")

    # Each funded 10000, contributed 2000, pot 6000 to member #1 (creator, round 1 recipient)
    b1 = db.get_user(p1)["balance"]
    b2 = db.get_user(p2)["balance"]
    b3 = db.get_user(p3)["balance"]
    if b1 != 14000:
        errors.append(f"User 1 balance expected 14000, got {b1}")
    if b2 != 8000:
        errors.append(f"User 2 balance expected 8000, got {b2}")
    if b3 != 8000:
        errors.append(f"User 3 balance expected 8000, got {b3}")

    t = db.get_tontine(tid)
    if not t:
        errors.append("Tontine not found after run.")
    else:
        if t["current_round"] != 2:
            errors.append(f"Expected current_round 2, got {t['current_round']}")
        members = db.get_members(tid)
        if any(m.get("paid_this_round") for m in members):
            errors.append("Expected paid flags reset after payout.")

    if errors:
        print("\nRESULT: FAIL")
        for e in errors:
            print(f" - {e}")
        raise SystemExit(1)

    print("\nRESULT: PASS")
    print(f"Verified: 3 members, 2000 sats/round, pot 6000 sats paid to member #1, balances [14000, 8000, 8000], round advanced to 2.")
    print(f"Demo DB: {DEMO_DB}")


if __name__ == "__main__":
    asyncio.run(run())
