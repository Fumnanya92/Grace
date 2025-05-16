from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
from twilio.rest import Client

from config import config

logger = logging.getLogger("payment")

DB_PATH = Path(config.DATA_DIR or ".") / "payments.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------#
# helpers ­– one shared executor for Twilio I/O so we remain async‑friendly   #
# ---------------------------------------------------------------------------#
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _twilio_async(fn, *args, **kwargs):
    """Run Twilio SDK call in thread‑pool."""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(_EXECUTOR, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------#
# PaymentHandler                                                             #
# ---------------------------------------------------------------------------#
class PaymentHandler:
    def __init__(self) -> None:
        self.twilio = Client(
            config.TWILIO["account_sid"], config.TWILIO["auth_token"]
        )
        self.whatsapp_from = config.TWILIO["whatsapp_number"]
        self.accountant_to = config.BUSINESS_RULES["accountant_contact"]

    # ----------------------------- DB utils --------------------------------
    async def _db(self):
        db = await aiosqlite.connect(DB_PATH)
        db.row_factory = aiosqlite.Row
        return db

    async def _ensure_tables(self):
        db = await self._db()
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id               INTEGER PRIMARY KEY,
                sender           TEXT,
                customer_name    TEXT,
                amount_due       INTEGER,
                verification_code TEXT,
                deposit_paid     INTEGER DEFAULT 0,
                payment_date     TEXT
            );
            """
        )
        await db.commit()

    # ------------------------- public entry points -------------------------
    async def process_user_message(self, sender: str, body: str) -> str:
        """Entry from WhatsApp webhook for **customers**."""
        await self._ensure_tables()

        body_l = body.lower()
        if any(k in body_l for k in ("account", "payment", "deposit")):
            return await self._start_payment_flow(sender)

        if await self._is_payment_proof(body):
            return await self._store_payment_proof(sender, body)

        return config.RESPONSES["payment"]["default"]

    async def process_accountant_message(self, body: str) -> None:
        """
        Entry from WhatsApp webhook for **accountant** number.

        Body format: `<4‑digit‑code> ok` or `1234 received`.
        """
        await self._ensure_tables()

        code = body.strip().split()[0]
        if not code.isdigit() or len(code) != 4:
            logger.info("Accountant message ignored – no 4‑digit code.")
            return

        await self._verify_and_acknowledge(code)

    # ---------------------------- workflow steps ---------------------------
    async def _start_payment_flow(self, sender: str) -> str:
        db = await self._db()
        cur = await db.execute(
            "SELECT deposit_paid FROM payments WHERE sender=? AND deposit_paid=0",
            (sender,),
        )
        if await cur.fetchone():
            return config.RESPONSES["payment"]["pending"]

        code = "".join(random.choices("0123456789", k=4))
        amount = int(
            config.PAYMENT["total_amount"]
            * config.PAYMENT.get("deposit_percentage", 0.5)
        )

        await db.execute(
            """
            INSERT INTO payments (sender, customer_name, amount_due, verification_code)
            VALUES (?,?,?,?)
            """,
            (sender, None, amount, code),
        )
        await db.commit()

        await self._alert_accountant(sender, amount, code)

        return config.RESPONSES["payment"]["instructions"].format(
            account_name=config.PAYMENT["account_name"],
            account_number=config.PAYMENT["account_number"],
            bank_name=config.PAYMENT["bank_name"],
            amount=amount,
        )

    async def _alert_accountant(self, sender: str, amount: int, code: str) -> None:
        body = (
            f"Payment alert ‑ {sender[-4:]}\n"
            f"Amount: ₦{amount:,}\n"
            f"Code: {code}\n\n"
            "Reply with the 4‑digit code once you see the money."
        )
        await _twilio_async(
            self.twilio.messages.create,
            body=body,
            from_=self.whatsapp_from,
            to=self.accountant_to,
        )
        logger.info("Sent accountant alert for %s code %s", sender, code)

    async def _store_payment_proof(self, sender: str, proof_text: str) -> str:
        # In a full build you would store the media SID / text –
        # kept simple here.
        return config.RESPONSES["payment"]["verification_sent"]

    async def _verify_and_acknowledge(self, code: str) -> None:
        db = await self._db()
        cur = await db.execute(
            "SELECT sender, customer_name, amount_due FROM payments WHERE verification_code=? AND deposit_paid=0",
            (code,),
        )
        row = await cur.fetchone()
        if not row:
            logger.warning("Code %s not found / already used.", code)
            return

        sender, name, amount = row["sender"], row["customer_name"], row["amount_due"]

        await db.execute(
            "UPDATE payments SET deposit_paid=1, payment_date=? WHERE verification_code=?",
            (datetime.utcnow().isoformat(), code),
        )
        await db.commit()

        msg = (
            f"Hi{' '+name if name else ''}! We’ve confirmed your ₦{amount:,} deposit. "
            "Thank you – we’ll start processing your order right away. ❤️"
        )
        await _twilio_async(
            self.twilio.messages.create,
            body=msg,
            from_=self.whatsapp_from,
            to=sender,
        )
        logger.info("Payment confirmed for %s code %s", sender, code)

    # ----------------------- helper / validators --------------------------
    async def _is_payment_proof(self, text: str) -> bool:
        kws = ("transfer", "paid", "receipt", "proof")
        return any(k in text.lower() for k in kws)
