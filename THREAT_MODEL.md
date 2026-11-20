# Threat Model — Tontine Lightning

This document summarizes the security posture of the current prototype (hackathon MVP). It is intentionally honest about what is implemented versus what remains a known limitation.

## System overview

Tontine Lightning is a custodial tontine (rotating savings group) bot/prototype. Users interact via a demo web simulator or (optionally) a WhatsApp webhook. The backend (FastAPI + SQLite) coordinates group membership, contribution state, and payout rounds.

- **Mock mode (`MOCK_MODE=true`, default):** balances and transfers are recorded in a local SQLite ledger only. No Bitcoin/Lightning network activity occurs.
- **Real mode (`MOCK_MODE=false`):** the app provisions wallets and performs invoice/payment operations through a configured [LNbits](https://lnbits.com/) instance. Actual settlement depends on the LNbits instance and its Lightning backend (e.g. regtest/testnet/mainnet).

## Assets

| Asset | Notes |
|---|---|
| User identity mapping | Phone number is used as input; only a SHA-256-derived hash (truncated) and last 4 digits are persisted for identification/display. |
| Wallet credentials | LNbits wallet IDs and keys (admin/invoice) stored in SQLite to operate custodial wallets on behalf of users. |
| Balances & pot funds | In mock mode: ledger values in DB. In real mode: funds held in LNbits wallets (custodial). |
| Tontine state | Group config, membership, round, and paid flags in SQLite. |
| Integration secrets | LNbits admin/faucet keys, WhatsApp tokens loaded from environment variables (not stored in DB). |

## Actors & threats

| Actor / threat | Examples | Relevance |
|---|---|---|
| Malicious/curious member | Tries to pay twice, underpay, join when full, view others' details | Core tontine logic abuse |
| Outsider / spammer | Floods commands to degrade service or enumerate groups | Availability / abuse |
| Compromised server or DB | Theft of wallet keys, tampering with balances/rounds, data exfiltration | High impact in custodial model |
| Network/MITM (webhook) | Tampered or spoofed webhook traffic if endpoint exposed without proper controls | WhatsApp integration risk |
| LNbits/operator/backend compromise | Loss/misdirection of funds, incorrect balances, downtime | Real-mode funds & availability |
| Custodian/operator | Misuse of stored wallet keys or privileged access | Inherent to custodial design |

## Mitigations implemented

- **Minimal identity storage:** raw phone numbers are not persisted; the app stores a phone hash (lookup key) and last 4 digits (masked display). Member views show `...<last4>` only.
- **Contribution/payout controls:** server-side checks for membership, sufficient balance (mock ledger or LNbits balance in real mode), amount bounds, member limits, and idempotent "already paid this round" handling before marking a contribution paid.
- **No single human pot-holder in logic:** contributions are accounted to a group pot (ledger deduction in mock mode; transfer to a dedicated tontine pot wallet in real mode) and payout is triggered only when all members have paid for the round.
- **Rate limiting:** basic in-memory sliding-window limit per phone identifier (`RATE_LIMIT_PER_MIN`, default 20/min) on message handling (simulator and webhook paths).
- **Database hygiene:** SQLite with WAL mode; schema avoids storing unnecessary fields (e.g. unused PIN). No intentional logging of phone numbers, tokens, wallet keys, or full invoices in normal paths.
- **Custodial disclosure:** user-facing registration/help text states the service is custodial and intended for small amounts.
- **Mode transparency:** UI and responses indicate mock vs real LNbits mode; funding in real mode shows/uses real Lightning invoices (and optional auto-pay for demos).

## Known limitations & out of scope

- **Custodial key storage:** LNbits wallet admin/invoice keys (and pot wallet keys) are stored in plaintext in the application database to enable automated transfers. There is no at-rest encryption, HSM, or secrets manager in this prototype. A DB/server compromise can expose keys.
- **No end-user authentication/authorization:** access is based on the provided phone number in the simulator/webhook payload; no PIN/OTP, no WhatsApp signature verification hardening beyond the verify token handshake shown, and the `/sim` demo endpoint is unauthenticated by design.
- **Rate limiting scope:** in-memory and per-process only (resets on restart; not shared across instances). Not a complete DoS defense.
- **Concurrency & integrity:** SQLite single-node design; limited protection against race conditions under concurrent payments/payouts. No double-entry ledger, no reconciliation jobs, and no dispute/rollback workflow.
- **Mock mode is not Bitcoin:** default demo mode simulates value transfer in a local ledger; it provides no Lightning settlement guarantees.
- **Real-mode dependencies:** correctness and fund safety depend on LNbits API behavior, version/extensions, configured Lightning backend, key permissions, and network conditions. Invoice settlement confirmation in some setups may require additional checks/webhooks not fully implemented here.
- **Privacy:** hashed identifiers reduce casual exposure but are not strong anonymization; metadata (timing, group membership patterns) remains in the DB/server.
- **Feature phones/USSD & localization:** not implemented (WhatsApp/web demo only; limited language support).

## Secure defaults & operational guidance

- Run demos with a **fresh, isolated `DATABASE`** file and `MOCK_MODE=true` unless intentionally testing real LNbits.
- For real mode, use **testnet/regtest or a dedicated low-value LNbits instance**, least-privilege keys, and never reuse production secrets.
- Keep `.env` secrets out of source control; rotate keys if exposed. Restrict access to the host running the app and its database.
- Treat this prototype as **not production-ready** for holding meaningful funds without significant additional controls (auth, encrypted key management, audited ledger, monitoring, and formal testing).