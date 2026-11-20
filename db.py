"""SQLite database — schema + query helpers."""

import hashlib
import sqlite3

from config import DATABASE


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            phone_hash  TEXT PRIMARY KEY,
            phone_last4 TEXT DEFAULT '',
            name        TEXT DEFAULT '',
            wallet_id   TEXT DEFAULT '',
            admin_key   TEXT DEFAULT '',
            invoice_key TEXT DEFAULT '',
            balance     INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tontines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            amount_sats     INTEGER NOT NULL,
            cycle_days      INTEGER DEFAULT 7,
            max_members     INTEGER DEFAULT 5,
            current_round   INTEGER DEFAULT 1,
            is_active       INTEGER DEFAULT 1,
            created_by      TEXT NOT NULL,
            pot_wallet_id   TEXT DEFAULT '',
            pot_admin_key   TEXT DEFAULT '',
            pot_invoice_key TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS members (
            tontine_id      INTEGER NOT NULL,
            phone_hash      TEXT NOT NULL,
            position        INTEGER NOT NULL,
            paid_this_round INTEGER DEFAULT 0,
            joined_at       TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tontine_id, phone_hash),
            FOREIGN KEY (tontine_id) REFERENCES tontines(id),
            FOREIGN KEY (phone_hash) REFERENCES users(phone_hash)
        );
        """
    )
    # Best-effort additive columns for older DBs (use a fresh DATABASE for demos).
    for stmt in [
        "ALTER TABLE users ADD COLUMN phone_last4 TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN invoice_key TEXT DEFAULT ''",
        "ALTER TABLE tontines ADD COLUMN pot_wallet_id TEXT DEFAULT ''",
        "ALTER TABLE tontines ADD COLUMN pot_admin_key TEXT DEFAULT ''",
        "ALTER TABLE tontines ADD COLUMN pot_invoice_key TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def hash_phone(phone: str) -> str:
    return hashlib.sha256(phone.strip().encode()).hexdigest()[:16]


def _last4(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits[-4:] if digits else phone.strip()[-4:]


# --- User CRUD ---


def create_user(phone: str, name: str = "") -> dict:
    conn = get_db()
    ph = hash_phone(phone)
    last4 = _last4(phone)
    conn.execute(
        "INSERT OR IGNORE INTO users (phone_hash, phone_last4, name) VALUES (?, ?, ?)",
        (ph, last4, name),
    )
    # Ensure last4 is set if row pre-existed without it
    conn.execute(
        "UPDATE users SET phone_last4=? WHERE phone_hash=? AND (phone_last4 IS NULL OR phone_last4='')",
        (last4, ph),
    )
    conn.commit()
    user = dict(conn.execute("SELECT * FROM users WHERE phone_hash=?", (ph,)).fetchone())
    conn.close()
    return user


def get_user(phone: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE phone_hash=?", (hash_phone(phone),)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_wallet(phone: str, wallet_id: str, admin_key: str, invoice_key: str = ""):
    conn = get_db()
    conn.execute(
        "UPDATE users SET wallet_id=?, admin_key=?, invoice_key=? WHERE phone_hash=?",
        (wallet_id, admin_key, invoice_key, hash_phone(phone)),
    )
    conn.commit()
    conn.close()


def update_balance(phone: str, amount: int):
    conn = get_db()
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE phone_hash=?",
        (amount, hash_phone(phone)),
    )
    conn.commit()
    conn.close()


def update_balance_by_hash(phone_hash: str, amount: int):
    conn = get_db()
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE phone_hash=?",
        (amount, phone_hash),
    )
    conn.commit()
    conn.close()


def get_balance(phone: str) -> int:
    user = get_user(phone)
    return int(user["balance"]) if user else 0


# --- Tontine CRUD ---


def create_tontine(name: str, amount: int, cycle_days: int, max_members: int, creator_phone: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tontines (name, amount_sats, cycle_days, max_members, created_by) VALUES (?,?,?,?,?)",
        (name, amount, cycle_days, max_members, hash_phone(creator_phone)),
    )
    tid = cur.lastrowid
    # creator is position 1
    conn.execute(
        "INSERT INTO members (tontine_id, phone_hash, position) VALUES (?,?,1)",
        (tid, hash_phone(creator_phone)),
    )
    conn.commit()
    conn.close()
    return tid


def update_tontine_pot(tontine_id: int, wallet_id: str, admin_key: str, invoice_key: str = ""):
    conn = get_db()
    conn.execute(
        "UPDATE tontines SET pot_wallet_id=?, pot_admin_key=?, pot_invoice_key=? WHERE id=?",
        (wallet_id, admin_key, invoice_key, tontine_id),
    )
    conn.commit()
    conn.close()


def join_tontine(tontine_id: int, phone: str) -> str:
    conn = get_db()
    t = conn.execute("SELECT * FROM tontines WHERE id=?", (tontine_id,)).fetchone()
    if not t:
        conn.close()
        return "Tontine not found."
    count = conn.execute("SELECT COUNT(*) as c FROM members WHERE tontine_id=?", (tontine_id,)).fetchone()["c"]
    if count >= t["max_members"]:
        conn.close()
        return "Tontine is full."
    ph = hash_phone(phone)
    existing = conn.execute(
        "SELECT 1 FROM members WHERE tontine_id=? AND phone_hash=?", (tontine_id, ph)
    ).fetchone()
    if existing:
        conn.close()
        return "You already joined this tontine."
    conn.execute(
        "INSERT INTO members (tontine_id, phone_hash, position) VALUES (?,?,?)",
        (tontine_id, ph, count + 1),
    )
    conn.commit()
    conn.close()
    return f"Joined tontine #{tontine_id} as member {count + 1}."


def get_tontine(tontine_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM tontines WHERE id=?", (tontine_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_members(tontine_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT m.*, u.phone_last4, u.name, u.wallet_id, u.admin_key, u.invoice_key
        FROM members m
        JOIN users u ON m.phone_hash = u.phone_hash
        WHERE m.tontine_id = ?
        ORDER BY m.position
        """,
        (tontine_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_paid(tontine_id: int, phone: str):
    conn = get_db()
    conn.execute(
        "UPDATE members SET paid_this_round=1 WHERE tontine_id=? AND phone_hash=?",
        (tontine_id, hash_phone(phone)),
    )
    conn.commit()
    conn.close()


def all_paid(tontine_id: int) -> bool:
    conn = get_db()
    unpaid = conn.execute(
        "SELECT COUNT(*) as c FROM members WHERE tontine_id=? AND paid_this_round=0",
        (tontine_id,),
    ).fetchone()["c"]
    conn.close()
    return unpaid == 0


def advance_round(tontine_id: int):
    conn = get_db()
    conn.execute("UPDATE tontines SET current_round = current_round + 1 WHERE id=?", (tontine_id,))
    conn.execute("UPDATE members SET paid_this_round = 0 WHERE tontine_id=?", (tontine_id,))
    conn.commit()
    conn.close()


def get_user_tontines(phone: str) -> list[dict]:
    conn = get_db()
    ph = hash_phone(phone)
    rows = conn.execute(
        "SELECT t.* FROM tontines t JOIN members m ON t.id=m.tontine_id WHERE m.phone_hash=? AND t.is_active=1",
        (ph,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_active_tontines() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM members WHERE tontine_id=t.id) as member_count FROM tontines t WHERE t.is_active=1 ORDER BY t.id DESC",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_demo_db():
    conn = get_db()
    conn.execute("DELETE FROM members")
    conn.execute("DELETE FROM tontines")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


# Initialize on import
init_db()
