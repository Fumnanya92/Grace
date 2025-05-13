from __future__ import annotations

import hmac, hashlib, base64, json, logging
from typing import Dict, Any

from fastapi import APIRouter, Header, HTTPException, status, Request
from twilio.rest import Client

from config import config

router = APIRouter(prefix="/webhook/shopify", tags=["shopify-webhooks"])
log = logging.getLogger("shopify.webhook")

# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #
def _verify_hmac(body: bytes, hmac_header: str) -> None:
    """Abort with 401 if the HMAC does not match Shopify's signature."""
    secret = config.SHOPIFY["webhook_secret"].encode()
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    if not hmac.compare_digest(expected, hmac_header):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")

def _send_whatsapp(to: str, message: str) -> None:
    client = Client(config.TWILIO["account_sid"], config.TWILIO["auth_token"])
    client.messages.create(
        from_=config.TWILIO["whatsapp_number"],
        to=f"whatsapp:{to}",
        body=message,
    )

# ------------------------------------------------------------------ #
# single POST endpoint – register **both** topics to same URL
# ------------------------------------------------------------------ #
@router.post("/")
async def shopify_webhook(
    request: Request,
    x_shopify_topic: str = Header(..., alias="X-Shopify-Topic"),
    x_shopify_hmac_sha256: str = Header(..., alias="X-Shopify-Hmac-Sha256"),
) -> Dict[str, str]:
    raw = await request.body()
    _verify_hmac(raw, x_shopify_hmac_sha256)

    payload: Dict[str, Any] = json.loads(raw)
    order_id = payload.get("id")

    # ── 1️⃣ order paid  ──────────────────────────────────────────────
    if x_shopify_topic == "orders/paid":
        log.info("Order %s paid", order_id)
        # nothing to notify yet – wait for fulfilment
        return {"status": "ack"}

    # ── 2️⃣ order fulfilled  ────────────────────────────────────────
    if x_shopify_topic == "orders/fulfilled":
        log.info("Order %s fulfilled", order_id)

        # find the original customer phone number
        phone = payload.get("customer", {}).get("phone")
        if not phone:
            log.warning("No phone on order %s – skip WhatsApp", order_id)
            return {"status": "no‑phone"}

        # craft a friendly message
        first_name = payload["customer"].get("first_name", "")
        tracking = payload["fulfillments"][0].get("tracking_numbers", [])
        track_txt = f"  • Tracking: {', '.join(tracking)}" if tracking else ""
        msg = (
            f"Hi {first_name}! 🎉  Your Grace order #{payload['name']} "
            f"has just been fulfilled and is on its way.\n{track_txt}\n\n"
            "Thank you for shopping with us!"
        )

        # fire WhatsApp
        _send_whatsapp(phone, msg)
        log.info("Notified %s for order %s", phone, order_id)
        return {"status": "sent"}

    # ── any other topic we haven't planned for ──────────────────────
    log.debug("Unhandled topic %s", x_shopify_topic)
    return {"status": "ignored"}
