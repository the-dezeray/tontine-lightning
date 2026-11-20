"""LNbits API wrapper.

- MOCK_MODE=true: no external calls; returns deterministic mock values.
- MOCK_MODE=false: calls a configured LNbits instance for real wallets/invoices/payments.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from config import (
    LNBITS_ADMIN_KEY,
    LNBITS_BEARER_TOKEN,
    LNBITS_PASSWORD,
    LNBITS_URL,
    LNBITS_USERNAME,
    MOCK_MODE,
)

_TIMEOUT = 20.0
_cached_bearer_token: str | None = None


def _mock_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


async def _get_bearer_token(client: httpx.AsyncClient) -> str | None:
    """Return a user-level bearer token for provisioning, if available/configured."""
    global _cached_bearer_token
    if LNBITS_BEARER_TOKEN:
        return LNBITS_BEARER_TOKEN
    if _cached_bearer_token:
        return _cached_bearer_token
    if not (LNBITS_USERNAME and LNBITS_PASSWORD):
        return None
    # Try common auth endpoints (LNbits versions differ)
    for path, body in [
        ("/api/v1/auth/login", {"username": LNBITS_USERNAME, "password": LNBITS_PASSWORD}),
        ("/api/v1/auth", {"username": LNBITS_USERNAME, "password": LNBITS_PASSWORD}),
    ]:
        try:
            r = await client.post(f"{LNBITS_URL}{path}", json=body)
            if r.status_code == 200:
                data = r.json()
                tok = data.get("access_token") or data.get("token")
                if tok:
                    _cached_bearer_token = str(tok)
                    return _cached_bearer_token
        except Exception:
            continue
    return None


async def create_wallet(name: str) -> dict[str, str]:
    """Create/provision a wallet. Returns {wallet_id, admin_key, invoice_key}."""
    if MOCK_MODE:
        base = f"mock_{name}"
        return {
            "wallet_id": _mock_id("w", base),
            "admin_key": _mock_id("adm", base),
            "invoice_key": _mock_id("inv", base),
        }

    if not LNBITS_ADMIN_KEY and not (LNBITS_USERNAME and LNBITS_PASSWORD) and not LNBITS_BEARER_TOKEN:
        raise RuntimeError("LNbits credentials required when MOCK_MODE=false (set LNBITS_ADMIN_KEY and/or LNBITS_USERNAME/PASSWORD)")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # 1) Try user-level bearer auth for wallet creation (needed on newer LNbits)
        bearer = await _get_bearer_token(client)
        if bearer:
            r = await client.post(
                f"{LNBITS_URL}/api/v1/wallet",
                headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
                json={"name": name},
            )
            if r.status_code == 200:
                data = r.json()
                return _normalize_wallet(data)
            # if bearer attempt fails, fall through to key-based attempts

        # 2) Try X-Api-Key (works on some setups)
        if LNBITS_ADMIN_KEY:
            headers = {"X-Api-Key": LNBITS_ADMIN_KEY, "Content-Type": "application/json"}
            r = await client.post(
                f"{LNBITS_URL}/api/v1/wallet",
                headers=headers,
                json={"name": name},
            )
            if r.status_code in (401, 403, 404, 405):
                # 3) Fallback: User Manager extension (if enabled)
                r = await client.post(
                    f"{LNBITS_URL}/usermanager/api/v1/users",
                    headers=headers,
                    json={
                        "admin_id": LNBITS_ADMIN_KEY,
                        "user_name": name,
                        "wallet_name": f"{name}-wallet",
                    },
                )
            r.raise_for_status()
            return _normalize_wallet(r.json())

    raise RuntimeError("Could not create LNbits wallet; check credentials/permissions")


def _normalize_wallet(data: Any) -> dict[str, str]:
    """Normalize known LNbits wallet response shapes."""
    if isinstance(data, dict) and "wallets" in data and data["wallets"]:
        w = data["wallets"][0]
        return {
            "wallet_id": str(w.get("id") or w.get("wallet_id") or ""),
            "admin_key": str(w.get("adminkey") or w.get("admin_key") or ""),
            "invoice_key": str(w.get("inkey") or w.get("invoice_key") or ""),
        }
    if isinstance(data, dict):
        return {
            "wallet_id": str(data.get("id") or data.get("wallet_id") or ""),
            "admin_key": str(data.get("adminkey") or data.get("admin_key") or ""),
            "invoice_key": str(data.get("inkey") or data.get("invoice_key") or ""),
        }
    return {"wallet_id": "", "admin_key": "", "invoice_key": ""}


async def get_balance(key: str) -> int:
    """Get wallet balance in sats for the given wallet key."""
    if MOCK_MODE:
        return 0
    if not key:
        raise RuntimeError("Wallet key missing for balance lookup")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{LNBITS_URL}/api/v1/wallet", headers={"X-Api-Key": key})
        r.raise_for_status()
        data = r.json()
    # LNbits returns msats
    return int(data.get("balance", 0)) // 1000


async def create_invoice(key: str, amount_sats: int, memo: str = "Tontine payment") -> dict[str, Any]:
    """Create a receive (incoming) Lightning invoice. Returns {payment_hash, payment_request}."""
    if MOCK_MODE:
        fake_hash = hashlib.sha256(f"{time.time()}-{amount_sats}-{memo}".encode()).hexdigest()
        return {"payment_hash": fake_hash, "payment_request": f"lnbc{amount_sats}mock1{fake_hash[:20]}"}

    if not key:
        raise RuntimeError("Wallet key missing for invoice creation")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
            json={"out": False, "amount": int(amount_sats), "memo": memo},
        )
        r.raise_for_status()
        data = r.json()
    return {
        "payment_hash": data.get("payment_hash") or data.get("checking_id") or "",
        "payment_request": data.get("payment_request") or data.get("bolt11") or "",
    }


async def pay_invoice(admin_key: str, bolt11: str) -> dict[str, Any]:
    """Pay a BOLT11 invoice. Returns provider response."""
    if MOCK_MODE:
        return {"payment_hash": "mock_paid", "status": "ok"}

    if not admin_key:
        raise RuntimeError("Wallet admin key missing for payment")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers={"X-Api-Key": admin_key, "Content-Type": "application/json"},
            json={"out": True, "bolt11": bolt11},
        )
        r.raise_for_status()
        return r.json()


async def internal_transfer(from_admin_key: str, to_key: str, amount_sats: int, memo: str) -> dict[str, Any]:
    """Transfer sats between wallets on the same LNbits instance by invoice+pay."""
    invoice = await create_invoice(to_key, amount_sats, memo=memo)
    pr = invoice.get("payment_request")
    if not pr:
        raise RuntimeError("Failed to create invoice for transfer")
    payment = await pay_invoice(from_admin_key, pr)
    return {"invoice": invoice, "payment": payment}
