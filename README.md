# Tontine Lightning

**Trust-minimized rotating savings groups (tontines) on Bitcoin Lightning — with a demo chat UI and WhatsApp-ready webhook.**

> Built for [Dakar Bitcoin Hack by BTrust](https://dakarhack.devpost.com)

## Problem

Tontines (rotating savings groups, common across Senegal and West Africa) help people save and access lump sums on a regular cycle. A core failure mode: **a treasurer or member holds the pooled cash and can delay, mismanage, or disappear with everyone’s money.**

**Primary user:** small savings groups (market vendors, families, community associations) of ~3–20 members contributing a fixed amount each week/month from a phone.

## Solution

Tontine Lightning coordinates the tontine lifecycle so contributions are tracked and payouts are executed by rules, not by a trusted pot-holder:

- Members register and receive a wallet (custodial, for small amounts).
- A group creator sets the contribution amount, cycle, and member count.
- Members join and pay each round; when all have paid, the **pot is automatically paid out** to that round’s recipient and the next round begins.
- Interface: a **web demo simulator** (works without external accounts) and a **WhatsApp Cloud API webhook** scaffold for messaging-based access.

### Impact (estimated, assumption-based)

Tontines/natts are widely used across West Africa by households and micro-entrepreneurs. A phone-accessible coordinator targeting groups of 3–20 members running recurring cycles can serve many contribution events per month per community (e.g. hundreds of groups → thousands of on-time, auditable round settlements). These figures are illustrative; calibrate with local partners and pilots.

## How it works (architecture)

```
Demo Web UI (/)  or  WhatsApp Cloud API
              │
              ▼
        FastAPI (app.py)
         /sim   /webhook
              │
           bot.py  ── command parsing, routing, per-phone rate limit
              │
         tontine.py ── group logic (create/join/pay/status/payout)
              │
      ┌───────┴────────┐
      ▼                ▼
   db.py            lnbits.py
  (SQLite:          (MOCK_MODE: simulated
   users/groups/     wallet/invoice/payment)
   rounds/state)         │
                    MOCK_MODE=false:
                    LNbits API (real wallets,
                    invoices, internal transfers)
```

- **Mock mode (`MOCK_MODE=true`, default):** fully offline. Wallets/invoices are simulated and balances are kept in a local SQLite ledger so the happy path is reproducible anywhere.
- **Real LNbits mode (`MOCK_MODE=false`):** provisions user and pot wallets via LNbits and performs real Lightning operations through the configured LNbits instance — balance lookups from LNbits, invoice creation for funding, and internal invoice+pay transfers for contributions (member → pot) and payouts (pot → recipient). Actual settlement depends on the LNbits instance/backend (regtest/testnet/mainnet).

## Quick start

### Prerequisites
- Python 3.10+ (or Docker)

### One-command verification (recommended)

Runs the full happy path on an isolated fresh database (mock mode), asserts expected outcomes, and exits `0` on success:

```bash
pip install -r requirements.txt
python demo.py
```

Expected: 3 members, 2000 sats/round, pot 6000 sats paid to member #1, balances `[14000, 8000, 8000]`, round advanced to 2, and `RESULT: PASS`.

(Windows PowerShell same commands; the script uses a temp demo DB automatically.)

### Run the demo UI

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:8000
```

Tip: change the **Phone** field to act as different members. Example flow:
1. `+221771234567`: `hi` → `fund 10000` → `create Famille 2000 weekly 3`
2. `+221772222222`: `hi` → `fund 10000` → `join 1`
3. `+221773333333`: `hi` → `fund 10000` → `join 1`
4. Each member: `pay` (last payment triggers auto-payout) → check `status` / `balance`

Use a fresh DB for a clean run if needed: PowerShell `$env:DATABASE="demo.db"; python app.py` (bash `DATABASE=demo.db python app.py`).

### Docker

```bash
docker build -t tontine-lightning .
docker run --rm -p 8000:8000 -e DATABASE=/tmp/demo.db tontine-lightning
# open http://localhost:8000
```

## Real LNbits mode (Bitcoin/Lightning integration)

To exercise real wallet/invoice/payment operations against an LNbits instance:

1. Copy env and configure:
   ```bash
   cp .env.example .env   # Windows: Copy-Item .env.example .env
   ```
2. Set in `.env`:
   - `MOCK_MODE=false`
   - `LNBITS_URL=https://<your-lnbits-host>`
   - `LNBITS_ADMIN_KEY=<key with permission to create wallets and pay>`
   - `FAUCET_ADMIN_KEY=<optional funding-wallet admin key>` — if set, `fund <sats>` auto-pays the generated receive invoice for one-command demos; if unset, `fund` returns a BOLT11 invoice to pay manually.
   - `DATABASE=demo.db` (fresh DB recommended)
3. Start the app and use the same commands. `balance` reads from LNbits; `pay` performs a real transfer to the tontine pot wallet; payout transfers from pot to the round recipient (payment hashes shown in responses).

**Notes:** behavior depends on your LNbits version/extensions and Lightning backend (use regtest/testnet/low-value setups for testing). Ensure the configured account can create wallets and send/receive payments.

## WhatsApp webhook (optional)

To connect WhatsApp Cloud API, set `WA_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_VERIFY_TOKEN` in `.env` and expose `GET/POST /webhook` publicly for Meta verification/delivery. Not required for the local demo.

## Bot commands

| Command | Example | Description |
|---|---|---|
| `hi` | `hi` | Register & provision wallet |
| `balance` | `balance` | Show balance (mock ledger or LNbits) |
| `fund` | `fund 10000` | Demo funding: mock credit, or LNbits invoice (auto-paid if faucet configured) |
| `create` | `create Famille 2000 weekly 3` | Create a tontine |
| `join` | `join 1` | Join a tontine by ID |
| `pay` | `pay` / `pay 1` | Contribute for the current round |
| `status` | `status` | Show round state and who paid |
| `help` | `help` | List commands |

## Security

- **Per-phone rate limiting** (in-memory sliding window, configurable via `RATE_LIMIT_PER_MIN`).
- **Masked identifiers:** raw phone numbers are not persisted; a phone hash and last 4 digits are stored/used for display.
- **Contribution safeguards:** membership/amount/balance checks and idempotent paid handling before recording contributions and triggering payout.
- **Custodial, small-amount prototype:** wallet keys are server-managed to automate flows.

See **[THREAT_MODEL.md](THREAT_MODEL.md)** for assets, threats, implemented mitigations, and known limitations. Treat this as **not production-ready** for meaningful funds.

## Constraints

- Custodial design; wallet/admin keys stored in the app database (no at-rest encryption/HSM in this prototype).
- Default mock mode simulates transfers in a local ledger (no network settlement); real mode depends on LNbits/backend configuration.
- Single-process, SQLite-based; limited concurrency/race handling and no dispute/rollback workflow.
- Demo UI and WhatsApp text flow (no USSD/feature-phone channel yet); limited localization.
- `/sim` endpoint is unauthenticated by design for local demos.

## Metrics to track

- `successful_rounds_completed` — rounds fully paid and paid out
- `contribution_settlement_time` — time from pay action to recorded/settled contribution
- `payment_success_rate` — successful vs failed contributions/payouts (and reasons)
- `groups_created`, `members_onboarded`
- (future) `dispute_rate`, `on_time_payment_rate`

## Submission materials

- **3-minute demo script:** [DEMO.md](DEMO.md)
- **Threat model:** [THREAT_MODEL.md](THREAT_MODEL.md)
- **One-command verification:** `python demo.py`

## What ships next

- Harden real Lightning settlement (testnet/regtest pilots, payment confirmations/webhooks, reconciliation)
- Stronger auth (PIN/OTP), encrypted key management, and audited ledgering
- Late-payment handling, disputes, and member lifecycle controls
- USSD / feature-phone access and local language support (e.g. Wolof, French)
- WhatsApp group flows and clearer non-custodial upgrade paths

## Tech stack

- Python, FastAPI, SQLite
- LNbits API integration (real mode) / mock ledger (default)
- WhatsApp Cloud API webhook scaffold
- Docker for one-command deployment

## License

MIT
