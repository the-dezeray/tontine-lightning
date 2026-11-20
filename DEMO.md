# Tontine Lightning — 3-Minute Demo Script

Target: ~3 minutes. Works with the one-command mock demo by default; call out real LNbits mode when configured.

## 0:00–0:30 — Problem (local impact)

- **Hook:** Across West Africa, millions of people use *tontines* (rotating savings groups) to save and access lump sums.
- **Pain:** A treasurer or member often holds the pooled cash. If they disappear, delay, or mismanage funds, the group loses money and trust.
- **Primary user:** Informal savings groups (market vendors, families, community associations) coordinating contributions on a regular cycle (weekly/monthly) via phones they already use.

## 0:30–1:30 — Solution (live demo)

**Setup (pre-demo):** `pip install -r requirements.txt` (or Docker). Default is **MOCK MODE** (offline, no external Lightning calls).

**Run the verifiable happy path:**
```bash
python demo.py
```
Narrate while it runs/prints:
1. **Register & wallet:** three members join; each gets a wallet in the app (and in real LNbits mode, a provisioned LNbits wallet).
2. **Create tontine:** User 1 creates `Famille`, 2000 sats, weekly, 3 members → group formed, pot rules fixed.
3. **Join:** Users 2 and 3 join the same tontine.
4. **Contribute:** each member pays the round contribution. In **mock mode** this updates a local custodial ledger; in **real LNbits mode** the app creates/pays Lightning invoices (internal transfers to a dedicated pot wallet) and shows payment hashes/real balances.
5. **Auto-payout:** when all members have paid, the pot (6000 sats) is automatically sent to the round’s recipient (member #1) and the round advances — no treasurer holds the funds.
6. **Verify:** balances end at `[14000, 8000, 8000]` sats and round advances to 2 (script prints `PASS`).

**Optional UI demo (if time):** open `python app.py` → http://localhost:8000, switch the phone number field to act as different members, and repeat `hi / fund / create / join / pay / status`.

## 1:30–2:15 — Impact

- **Workflow change:** replaces "trust a person with the pot" with rule-based, automated collection and payout.
- **Why Bitcoin/Lightning:** fast, low-friction transfers suited to small, frequent contributions; path to real settlement and interoperability when connected to a Lightning backend.
- **Estimated reach (illustrative):** tontines/natts are widely used across Senegal and West Africa by households and micro-entrepreneurs. A lightweight, phone-accessible coordinator can target small groups (e.g. 3–20 members) running recurring cycles; even hundreds of active groups translate to thousands of contribution events per month. *(State assumptions; calibrate with local partner data post-hackathon.)*

## 2:15–3:00 — What’s real, constraints, and next steps

- **What’s implemented now:** end-to-end tontine lifecycle, demo UI + WhatsApp webhook scaffold, per-phone rate limiting, masked identifiers (hash + last4), and an LNbits-backed real mode (wallet provisioning, real balance lookups, invoice creation/payment for contributions & payout when configured). Default demo runs in **mock mode** for offline reproducibility.
- **Constraints / honesty:** custodial prototype; wallet keys stored server-side (see `THREAT_MODEL.md`); real-mode security/correctness depends on the LNbits instance/backend; not production-ready for significant funds.
- **Metrics to track:** `successful_rounds_completed`, `contribution_settlement_time`, `payment_success_rate` (and failure reasons), `groups_created`, `members_onboarded`.
- **Next iteration:** harden real Lightning settlement and confirmations (testnet/regtest pilots), add auth/PIN and dispute/late-payment handling, USSD/feature-phone & local language support, group chat flows, and stronger key management/audited ledger before any mainnet use.