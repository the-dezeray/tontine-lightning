"""Tontine business logic — create, join, pay, payout."""

from __future__ import annotations

import db
import lnbits
from config import FAUCET_ADMIN_KEY, LNBITS_ADMIN_KEY, MOCK_MODE, XOF_PER_SAT


def fmt(sats: int) -> str:
    """Format sats with XOF equivalent."""
    xof = int(sats * XOF_PER_SAT)
    return f"{sats:,} sats (~{xof:,} XOF)"


def _mode_label() -> str:
    return "mock" if MOCK_MODE else "lnbits"


async def _get_balance_sats(user: dict) -> int:
    if MOCK_MODE:
        return int(user.get("balance", 0))
    key = user.get("admin_key") or user.get("invoice_key")
    if not key:
        return int(user.get("balance", 0))
    return await lnbits.get_balance(key)


async def register_user(phone: str) -> str:
    user = db.get_user(phone)
    if user and user.get("wallet_id"):
        bal = await _get_balance_sats(user)
        return f"Welcome back! Your balance: {fmt(bal)}"

    if not user:
        user = db.create_user(phone)

    try:
        wallet = await lnbits.create_wallet(db.hash_phone(phone))
        db.update_user_wallet(
            phone,
            wallet.get("wallet_id", ""),
            wallet.get("admin_key", ""),
            wallet.get("invoice_key", ""),
        )
    except Exception as e:
        if MOCK_MODE:
            # mock should not fail, but be safe
            db.update_user_wallet(phone, f"mock_{db.hash_phone(phone)}", "", "")
        else:
            return f"Wallet setup failed: {e}\nCheck LNbits config (LNBITS_URL/LNBITS_ADMIN_KEY, MOCK_MODE)."

    mode_note = "(demo/mock mode)" if MOCK_MODE else "(real LNbits mode)"
    return (
        "Welcome to Tontine Lightning!\n"
        f"Your Bitcoin wallet is ready {mode_note}.\n\n"
        "This is a custodial service for small amounts.\n"
        "Commands: balance, create, join, pay, status, fund, help"
    )


async def handle_balance(phone: str) -> str:
    user = db.get_user(phone)
    if not user or not user.get("wallet_id"):
        return await register_user(phone)

    try:
        bal = await _get_balance_sats(user)
    except Exception as e:
        return f"Could not fetch balance: {e}"

    tontines = db.get_user_tontines(phone)
    mode = "mock ledger" if MOCK_MODE else "LNbits wallet"
    msg = f"Balance: {fmt(bal)} [{mode}]\n"
    if tontines:
        msg += f"Active tontines: {len(tontines)}"
    if not MOCK_MODE and user.get("wallet_id"):
        msg += f"\nWallet: {str(user['wallet_id'])[:8]}..."
    return msg


async def handle_create(phone: str, args: list[str]) -> str:
    # create <name> <amount_sats> <weekly|monthly> <max_members>
    if len(args) < 4:
        return "Usage: create <name> <amount_sats> <weekly|monthly> <max_members>\nExample: create Famille 5000 weekly 5"

    name = args[0]
    try:
        amount = int(args[1])
        cycle = 7 if args[2].lower().startswith("w") else 30
        max_m = int(args[3])
    except ValueError:
        return "Invalid numbers. Example: create Famille 5000 weekly 5"

    if max_m < 2 or max_m > 20:
        return "Members must be between 2 and 20."
    if amount < 100 or amount > 100_000:
        return "Amount must be between 100 and 100,000 sats."

    tid = db.create_tontine(name, amount, cycle, max_m, phone)
    pot_note = ""
    if not MOCK_MODE:
        try:
            pot = await lnbits.create_wallet(f"pot-{tid}-{name}")
            db.update_tontine_pot(
                tid,
                pot.get("wallet_id", ""),
                pot.get("admin_key", ""),
                pot.get("invoice_key", ""),
            )
            pot_note = f"\nPot wallet: {str(pot.get('wallet_id',''))[:8]}... (LNbits)"
        except Exception as e:
            pot_note = f"\nWarning: could not create pot wallet: {e}"

    return (
        f"Tontine '{name}' created! (ID: {tid})\n"
        f"Amount: {fmt(amount)} per round\n"
        f"Members: 1/{max_m}\n"
        f"Cycle: {'weekly' if cycle == 7 else 'monthly'}\n"
        f"Share: tell others to send 'join {tid}'"
        f"{pot_note}"
    )


async def handle_join(phone: str, args: list[str]) -> str:
    if not args:
        return "Usage: join <tontine_id>\nExample: join 1"
    try:
        tid = int(args[0])
    except ValueError:
        return "Invalid tontine ID."

    result = db.join_tontine(tid, phone)
    t = db.get_tontine(tid)
    if t:
        members = db.get_members(tid)
        result += f"\nMembers: {len(members)}/{t['max_members']}"
    return result


async def handle_pay(phone: str, args: list[str]) -> str:
    tontines = db.get_user_tontines(phone)
    if not tontines:
        return "You're not in any tontine. Use 'join <id>' first."

    # If multiple tontines, pick the one specified or the first
    if args:
        try:
            tid = int(args[0])
        except ValueError:
            return "Usage: pay [tontine_id]"
    else:
        tid = tontines[0]["id"]

    t = db.get_tontine(tid)
    if not t:
        return "Tontine not found."

    user = db.get_user(phone)
    if not user:
        return await register_user(phone)

    amount = int(t["amount_sats"])

    # Check if already paid
    members = db.get_members(tid)
    me = next((m for m in members if m["phone_hash"] == db.hash_phone(phone)), None)
    if not me:
        return "You're not a member of this tontine."
    if me["paid_this_round"]:
        return f"You already paid for round {t['current_round']}."

    # Payment execution
    try:
        if MOCK_MODE:
            bal = int(user.get("balance", 0))
            if bal < amount:
                return f"Insufficient balance. Need {fmt(amount)}, have {fmt(bal)}.\nUse 'fund <sats>' in demo mode."
            db.update_balance(phone, -amount)
            pay_note = ""
        else:
            # Real LNbits: transfer from member wallet to pot wallet
            user_key = user.get("admin_key")
            pot_receive_key = t.get("pot_invoice_key") or t.get("pot_admin_key")
            pot_pay_key = t.get("pot_admin_key")
            if not user_key:
                return "Your wallet is not configured for payments (missing key). Re-register or check LNbits setup."
            if not pot_receive_key or not pot_pay_key:
                return "This tontine has no pot wallet configured for real mode. Recreate it with MOCK_MODE=false and a working LNbits setup."
            bal = await lnbits.get_balance(user_key)
            if bal < amount:
                return f"Insufficient LNbits balance. Need {fmt(amount)}, have {fmt(bal)}."
            transfer = await lnbits.internal_transfer(
                user_key,
                pot_receive_key,
                amount,
                memo=f"Tontine {t['name']} #{tid} round {t['current_round']}",
            )
            phash = ((transfer.get("invoice") or {}).get("payment_hash") or "")
            pay_note = f"\nLightning payment: {phash[:16]}..." if phash else "\nLightning transfer completed (LNbits)."
    except Exception as e:
        return f"Payment failed: {e}"

    db.mark_paid(tid, phone)

    msg = f"Paid {fmt(amount)} for round {t['current_round']}!{pay_note if not MOCK_MODE else ''}"

    # Check if all members paid -> trigger payout
    if db.all_paid(tid):
        payout_msg = await _do_payout(tid)
        msg += "\n\n" + payout_msg

    return msg


async def _do_payout(tontine_id: int) -> str:
    t = db.get_tontine(tontine_id)
    if not t:
        return "Payout failed: tontine not found."
    members = db.get_members(tontine_id)
    if not members:
        return "Payout failed: no members."
    round_num = int(t["current_round"])

    # Find recipient: member whose position == current_round (mod members)
    recipient_pos = ((round_num - 1) % len(members)) + 1
    recipient = next(m for m in members if m["position"] == recipient_pos)

    pot = int(t["amount_sats"]) * len(members)

    payout_note = ""
    try:
        if MOCK_MODE:
            db.update_balance_by_hash(recipient["phone_hash"], pot)
        else:
            pot_pay_key = t.get("pot_admin_key")
            recv_key = recipient.get("invoice_key") or recipient.get("admin_key")
            if not pot_pay_key or not recv_key:
                return "Payout failed: missing LNbits wallet keys for pot/recipient."
            transfer = await lnbits.internal_transfer(
                pot_pay_key,
                recv_key,
                pot,
                memo=f"Tontine {t['name']} #{tontine_id} payout round {round_num}",
            )
            phash = ((transfer.get("invoice") or {}).get("payment_hash") or "")
            payout_note = f"\nPayout payment: {phash[:16]}..." if phash else "\nPayout transferred via LNbits."
    except Exception as e:
        return f"Payout failed: {e}. Contributions recorded; round not advanced."

    # Advance to next round
    db.advance_round(tontine_id)

    who = recipient.get("phone_last4") or "????"
    return (
        f"ALL PAID! Round {round_num} complete!\n"
        f"Pot of {fmt(pot)} sent to member #{recipient_pos} (...{who}).\n"
        f"Next round: {round_num + 1}"
        f"{payout_note}"
    )


async def handle_status(phone: str, args: list[str]) -> str:
    tontines = db.get_user_tontines(phone)
    if not tontines:
        return "You're not in any tontine yet."

    if args:
        try:
            tid = int(args[0])
        except ValueError:
            return "Usage: status [tontine_id]"
        tontines = [t for t in tontines if t["id"] == tid]
        if not tontines:
            return "Tontine not found (or you're not a member)."

    msgs = []
    for t in tontines:
        members = db.get_members(t["id"])
        if not members:
            continue
        recipient_pos = ((t["current_round"] - 1) % len(members)) + 1
        paid = sum(1 for m in members if m["paid_this_round"])

        mode = "mock" if MOCK_MODE else "lnbits"
        lines = [
            f"Tontine: {t['name']} (#{t['id']}) [{mode}]",
            f"Round: {t['current_round']} | Amount: {fmt(int(t['amount_sats']))}",
            f"Paid: {paid}/{len(members)}",
            f"This round's recipient: member #{recipient_pos}",
            "",
        ]
        for m in members:
            check = "OK" if m["paid_this_round"] else ".."
            star = " <- recipient" if m["position"] == recipient_pos else ""
            last4 = m.get("phone_last4") or "????"
            lines.append(f"  #{m['position']} ...{last4} [{check}]{star}")

        msgs.append("\n".join(lines))

    return "\n\n".join(msgs)


async def handle_fund(phone: str, args: list[str]) -> str:
    """Fund wallet: mock ledger credit, or real LNbits invoice (auto-paid if faucet configured)."""
    if not args:
        return "Usage: fund <amount_sats>\nExample: fund 10000"
    try:
        amount = int(args[0])
    except ValueError:
        return "Invalid amount."
    if amount < 1 or amount > 1_000_000:
        return "Amount must be 1-1,000,000 sats."

    user = db.get_user(phone)
    if not user or not user.get("wallet_id"):
        await register_user(phone)
        user = db.get_user(phone)

    if MOCK_MODE:
        db.update_balance(phone, amount)
        bal = db.get_balance(phone)
        return f"Added {fmt(amount)} (demo/mock mode)\nNew balance: {fmt(bal)}"

    # Real mode: create invoice on user's wallet
    recv_key = (user or {}).get("invoice_key") or (user or {}).get("admin_key")
    if not recv_key:
        return "Wallet not configured for receiving. Check LNbits setup."
    try:
        inv = await lnbits.create_invoice(recv_key, amount, memo="Tontine demo fund")
        bolt11 = inv.get("payment_request", "")
        phash = inv.get("payment_hash", "")
    except Exception as e:
        return f"Failed to create funding invoice: {e}"

    faucet_key = FAUCET_ADMIN_KEY or LNBITS_ADMIN_KEY
    if faucet_key and bolt11:
        try:
            await lnbits.pay_invoice(faucet_key, bolt11)
            bal = await lnbits.get_balance(recv_key)
            return (
                f"Funded {fmt(amount)} via LNbits (invoice auto-paid for demo).\n"
                f"Payment: {phash[:16]}...\n"
                f"New balance: {fmt(bal)}"
            )
        except Exception:
            # Fall through to showing invoice
            pass

    # Show invoice for manual payment
    preview = bolt11 if len(bolt11) <= 120 else bolt11[:120] + "..."
    return (
        f"Funding invoice created for {fmt(amount)} (LNbits).\n"
        f"Pay this BOLT11 from any Lightning wallet, then check 'balance':\n\n"
        f"{preview}\n\n"
        f"payment_hash: {phash}"
    )


HELP_TEXT = """Tontine Lightning — Commands:

balance — Check your wallet balance
create <name> <sats> <weekly|monthly> <members> — Start a tontine
join <id> — Join a tontine group
pay [id] — Pay your contribution this round
status [id] — See tontine status & who paid
fund <sats> — Add sats (mock credit, or LNbits invoice in real mode)
help — Show this message"""
