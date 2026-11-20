"""Configuration — loads from .env or environment variables."""

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# LNbits (real mode: set MOCK_MODE=false and provide a reachable LNbits instance)
LNBITS_URL = os.getenv("LNBITS_URL", "https://legend.lnbits.com").rstrip("/")
# Wallet/admin API key (X-Api-Key). Also used as faucet fallback if FAUCET_ADMIN_KEY unset.
LNBITS_ADMIN_KEY = os.getenv("LNBITS_ADMIN_KEY", "")
# Optional: funding wallet admin key used to auto-pay "fund" invoices in real-mode demos
FAUCET_ADMIN_KEY = os.getenv("FAUCET_ADMIN_KEY", "")
# Optional: user-level auth for wallet provisioning on LNbits versions that require it
# (e.g. POST /api/v1/wallet with Bearer token). If set, used for wallet creation.
LNBITS_USERNAME = os.getenv("LNBITS_USERNAME", "")
LNBITS_PASSWORD = os.getenv("LNBITS_PASSWORD", "")
LNBITS_BEARER_TOKEN = os.getenv("LNBITS_BEARER_TOKEN", "")

# WhatsApp Cloud API
WA_TOKEN = os.getenv("WA_TOKEN", "")
WA_VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "tontine_verify_2026")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")

# App
_default_db = str(BASE_DIR / "tontine.db")
# Fall back to temp dir if project dir isn't writable
try:
    import sqlite3 as _sq

    _c = _sq.connect(_default_db)
    _c.execute("CREATE TABLE IF NOT EXISTS _test_write (id INT)")
    _c.close()
except Exception:
    _default_db = os.path.join(tempfile.gettempdir(), "tontine.db")
DATABASE = os.getenv("DATABASE", _default_db)
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
XOF_PER_SAT = 4.0  # approximate CFA franc per sat for display

# Security
MAX_BALANCE_SATS = 1_000_000  # 0.01 BTC cap
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))
