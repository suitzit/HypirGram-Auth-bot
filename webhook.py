import hashlib
import hmac
import json
import logging
import os
import re
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiohttp import web
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.engine import SessionLocal
from database.models import OtpDelivery, Users

load_dotenv()

logger = logging.getLogger(__name__)

SECRET = os.getenv("OTP_WEBHOOK_SECRET")
MAX_SKEW_SECONDS = 300
PROCESSING_TIMEOUT = 300


async def health_check(request):
    return web.json_response({
        "status": "ok",
        "service": "HypirGram Auth Bot"
    })


async def otp_delivery(request):
    if not SECRET:
        logger.error("OTP_WEBHOOK_SECRET is not configured")
        return web.json_response(
            {"error": "server_not_configured"},
            status=503
        )

    raw_body = await request.read()

    timestamp = request.headers.get("X-Telesrv-Timestamp", "")
    signature = request.headers.get("X-Telesrv-Signature", "")
    idempotency_key = request.headers.get("Idempotency-Key", "")

    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError):
        return web.json_response(
            {"error": "invalid_timestamp"},
            status=401
        )

    if abs(time.time() - timestamp_value) > MAX_SKEW_SECONDS:
        return web.json_response(
            {"error": "expired_timestamp"},
            status=401
        )

    signed_data = timestamp.encode() + b"." + raw_body

    expected_signature = "sha256=" + hmac.new(
        SECRET.encode(),
        signed_data,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return web.json_response(
            {"error": "invalid_signature"},
            status=401
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return web.json_response(
            {"error": "invalid_json"},
            status=400
        )

    if not isinstance(payload, dict):
        return web.json_response(
            {"error": "invalid_payload"},
            status=400
        )

    required_fields = (
        "version",
        "delivery_id",
        "purpose",
        "channel",
        "recipient",
        "code",
        "expires_at",
        "expires_in",
    )

    if any(field not in payload for field in required_fields):
        return web.json_response(
            {"error": "missing_fields"},
            status=400
        )

    delivery_id = payload["delivery_id"]

    if payload["version"] != "1":
        return web.json_response(
            {"error": "unsupported_version"},
            status=400
        )

    if not isinstance(delivery_id, str) or not delivery_id:
        return web.json_response(
            {"error": "invalid_delivery_id"},
            status=400
        )

    logger.info(
        "OTP webhook received: keys=%s version=%r purpose=%r "
        "channel=%r expires_in_type=%s",
        sorted(payload.keys()),
        payload.get("version"),
        payload.get("purpose"),
        payload.get("channel"),
        type(payload.get("expires_in")).__name__,
    )

    if idempotency_key != delivery_id:
        return web.json_response(
            {"error": "idempotency_key_mismatch"},
            status=400
        )

    if payload["purpose"] != "login_sms":
        return web.json_response(
            {"error": "unsupported_purpose"},
            status=400
        )

    if payload["channel"] != "sms":
        return web.json_response(
            {"error": "unsupported_channel"},
            status=400
        )

    recipient = payload["recipient"]
    code = payload["code"]

    if not isinstance(recipient, str) or not isinstance(code, str):
        return web.json_response(
            {"error": "invalid_recipient_or_code"},
            status=400
        )

    phone = re.sub(r"\D", "", recipient)

    if not phone or not code.isdigit() or not 4 <= len(code) <= 10:
        return web.json_response(
            {"error": "invalid_recipient_or_code"},
            status=400
        )

    try:
        expires_in = int(payload["expires_in"])
    except (TypeError, ValueError):
        return web.json_response(
            {"error": "invalid_expiration"},
            status=400
        )

    if expires_in <= 0:
        return web.json_response(
            {"error": "code_expired"},
            status=400
        )

    now = time.time()

    # Проверяем, не обрабатывали ли мы эту доставку раньше.
    async with SessionLocal() as session:
        result = await session.execute(
            select(OtpDelivery).where(
                OtpDelivery.delivery_id == delivery_id
            )
        )
        delivery = result.scalar_one_or_none()

        if delivery is not None:
            if delivery.status == "sent":
                return web.json_response({
                    "accepted": True,
                    "duplicate": True
                })

            if (
                delivery.status == "processing"
                and now - delivery.updated_at < PROCESSING_TIMEOUT
            ):
                return web.json_response(
                    {"error": "delivery_in_progress"},
                    status=409
                )

            delivery.status = "processing"
            delivery.updated_at = now
            await session.commit()

        else:
            delivery = OtpDelivery(
                delivery_id=delivery_id,
                status="processing",
                updated_at=now
            )
            session.add(delivery)

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return web.json_response(
                    {"error": "delivery_in_progress"},
                    status=409
                )

    # Ищем Telegram-пользователя по номеру.
    async with SessionLocal() as session:
        result = await session.execute(
            select(Users).where(Users.phone == phone)
        )
        user = result.scalar_one_or_none()

    if user is None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(OtpDelivery).where(
                    OtpDelivery.delivery_id == delivery_id
                )
            )
            delivery = result.scalar_one_or_none()

            if delivery:
                delivery.status = "failed"
                delivery.updated_at = time.time()
                await session.commit()

        return web.json_response(
            {"error": "user_not_found"},
            status=404
        )

    # Отправляем код через Telegram.
    try:
        chat_id = int(user.user_id)

        await request.app["bot"].send_message(
            chat_id=chat_id,
            text=(
                "💬 Ваш код авторизации HypirGram:\n\n"
                f"<code>{code}</code>\n\n"
                "Никому не сообщайте этот код."
            ),
            parse_mode="HTML"
        )

    except (ValueError, TelegramAPIError):
        logger.exception("Telegram OTP delivery failed")

        async with SessionLocal() as session:
            result = await session.execute(
                select(OtpDelivery).where(
                    OtpDelivery.delivery_id == delivery_id
                )
            )
            delivery = result.scalar_one_or_none()

            if delivery:
                delivery.status = "failed"
                delivery.updated_at = time.time()
                await session.commit()

        return web.json_response(
            {"error": "telegram_delivery_failed"},
            status=502
        )

    # Отмечаем доставку как завершённую.
    async with SessionLocal() as session:
        result = await session.execute(
            select(OtpDelivery).where(
                OtpDelivery.delivery_id == delivery_id
            )
        )
        delivery = result.scalar_one_or_none()

        if delivery:
            delivery.status = "sent"
            delivery.updated_at = time.time()
            await session.commit()

    logger.info(
        "OTP delivered successfully | delivery_id=%s",
        delivery_id
    )

    return web.json_response({"accepted": True}, status=200)


def create_app(bot: Bot):
    app = web.Application(client_max_size=64 * 1024)

    app["bot"] = bot

    app.router.add_get("/health", health_check)
    app.router.add_post("/v1/otp/deliveries", otp_delivery)

    return app
