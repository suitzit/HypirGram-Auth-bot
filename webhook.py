import asyncio
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
    async def delete_message_after(bot: Bot, chat_id: int, message_id: int):
        await asyncio.sleep(300)  # 5 минут

        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
        except TelegramAPIError:
            logger.exception("Failed to delete OTP message")

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

        sent_message = await request.app["bot"].send_message(
            chat_id=chat_id,
            text=(
                "💬 Ваш код авторизации HypirGram:\n\n"
                f"<code>{code}</code>\n\n"
                "Никому не сообщайте этот код."
            ),
            parse_mode="HTML"
        )

        asyncio.create_task(
            delete_message_after(
                request.app["bot"],
                chat_id,
                sent_message.message_id
            )
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


# =====================================================================
# =====================================================================
#                 РАСШИРЕНИЕ: УПРАВЛЕНИЕ АККАУНТАМИ
#           (всё, что выше, — исходный код без изменений)
# =====================================================================
# =====================================================================
#
# Что добавлено ниже (всё в одном файле, исходный код не тронут):
#   1. grant_stars()                    — выдача звёзд
#   2. mint_collectible_username()      — выдача NFT-юзернейма
#   3. give_gift()                      — выдача подарка / NFT-подарка
#   4. get_user_purchased_numbers()     — номера, купленные пользователем
#   5. Комментарий про выдачу номера    — см. блок «ВЫДАЧА НОМЕРА»
#   6. Необязательные HTTP-эндпоинты    — register_admin_routes()
#
# ---------------------------------------------------------------------
# КАК ЭТО РАБОТАЕТ
# ---------------------------------------------------------------------
# Админка OwpenGram (порт 2600) — это только веб-интерфейс. Все изменения
# она отправляет в Admin API основного сервера. Мы обращаемся к тому же
# Admin API напрямую с Bearer-токеном — результат тот же, что и кнопка
# в админке (звёзды, юзернеймы, подарки), но без браузера и CSRF.
#
# ---------------------------------------------------------------------
# ПОДСКАЗКИ ПО ПОДКЛЮЧЕНИЮ
# ---------------------------------------------------------------------
# [1] .env сервера OwpenGram (owpengram-server-main/.env) — включите
#     Admin API и задайте токен (по умолчанию он ОТКЛЮЧЁН):
#
#         TELESRV_ADMIN_API_ADDR=127.0.0.1:2700
#         TELESRV_ADMIN_API_TOKEN=длинный_случайный_токен
#
#     Тот же токен должен быть у админки (cmd/telesrv-admin). После
#     изменения перезапустите ./owpengram-server.sh. Порт 2700 — пример,
#     возьмите любой свободный и держите его на loopback.
#
# [2] .env этого бота (рядом с OTP_WEBHOOK_SECRET):
#
#         OWPEN_ADMIN_API_URL=http://127.0.0.1:2700
#         OWPEN_ADMIN_API_TOKEN=тот_же_токен_что_в_п.1
#         ACTIONS_WEBHOOK_SECRET=отдельный_секрет_для_эндпоинтов  # только для HTTP
#
#     Если бот и сервер на разных машинах (например, через Tailscale),
#     укажите tailnet-адрес в OWPEN_ADMIN_API_URL и откройте Admin API
#     не на loopback, а на tailnet-IP (TELESRV_ADMIN_API_ADDR=100.x.y.z:2700).
#
# [3] Главный файл бота. Вместо
#
#         app = create_app(bot)
#
#     можно написать (старая create_app не меняется):
#
#         from webhook import create_app_extended
#         app = create_app_extended(bot)
#
#     или оставить create_app как есть и добавить одну строку:
#
#         from webhook import create_app, register_admin_routes
#         app = create_app(bot)
#         register_admin_routes(app)
#
#     Если HTTP-эндпоинты вам не нужны, ничего подключать не требуется:
#     просто импортируйте функции и вызывайте их из хендлеров бота:
#
#         from webhook import grant_stars, give_gift
#         await grant_stars(user.user_id, 100, reason="Оплата #123",
#                           command_id="stars-pay-123")
#
# [4] Зависимости: aiohttp уже стоит (он нужен для сервера выше).
#     Дополнительных пакетов не требуется.
#
# ---------------------------------------------------------------------
# ВАЖНО
# ---------------------------------------------------------------------
# * command_id — ключ идемпотентности. Повтор запроса с тем же command_id
#   НЕ выполнит действие второй раз. Для оплат передавайте стабильный id
#   (например, f"stars-{payment_id}"), иначе при повторе платежа звёзды
#   начислятся дважды.
# * user_id — это ID пользователя на сервере OwpenGram (тот же, что у вас
#   в Users.user_id), а не номер телефона.
# * Не открывайте Admin API в интернет: токен даёт полные права.
# =====================================================================

import uuid

import aiohttp

# --- Настройки расширения ---------------------------------------------

# Адрес Admin API основного сервера (TELESRV_ADMIN_API_ADDR).
OWPEN_ADMIN_API_URL = (os.getenv("OWPEN_ADMIN_API_URL") or "").rstrip("/")
# Bearer-токен (TELESRV_ADMIN_API_TOKEN).
OWPEN_ADMIN_API_TOKEN = os.getenv("OWPEN_ADMIN_API_TOKEN")
# Секрет подписи для HTTP-эндпоинтов ниже. Не равен OTP_WEBHOOK_SECRET
# намеренно: утечка кода доставки не должна давать право выдавать звёзды.
ACTIONS_SECRET = os.getenv("ACTIONS_WEBHOOK_SECRET")
# Имя оператора в журнале аудита сервера.
ADMIN_ACTOR = "hypirgram-bot"
ADMIN_API_TIMEOUT = 15

# SQL для получения купленных пользователем номеров из БАЗЫ БОТА.
# !!! ИЗМЕНИТЕ под свою таблицу !!! Нужны колонки phone и purchased_at,
# параметр :user_id. Здесь пример для таблицы purchased_numbers.
PURCHASED_NUMBERS_SQL = (
    "SELECT phone, purchased_at "
    "FROM purchased_numbers "
    "WHERE user_id = :user_id "
    "ORDER BY purchased_at DESC"
)


class AdminAPIError(Exception):
    """Admin API вернул ошибку или недоступен."""

    def __init__(self, status: int, body):
        super().__init__(f"Admin API error {status}: {body}")
        self.status = status
        self.body = body


async def _admin_request(method: str, path: str, payload=None, params=None):
    """Один запрос к Admin API с Bearer-токеном. Возвращает JSON-ответ."""
    if not OWPEN_ADMIN_API_URL or not OWPEN_ADMIN_API_TOKEN:
        raise AdminAPIError(
            503,
            "OWPEN_ADMIN_API_URL / OWPEN_ADMIN_API_TOKEN не настроены",
        )

    headers = {"Authorization": f"Bearer {OWPEN_ADMIN_API_TOKEN}"}
    timeout = aiohttp.ClientTimeout(total=ADMIN_API_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.request(
                method,
                OWPEN_ADMIN_API_URL + path,
                json=payload,
                params=params,
                headers=headers,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {"raw": await resp.text()}

                if resp.status >= 400:
                    raise AdminAPIError(resp.status, data)
                return data
    except aiohttp.ClientError as exc:
        raise AdminAPIError(502, f"Admin API недоступен: {exc}") from exc


def _command_meta(reason: str, command_id: str | None) -> dict:
    """Общие поля любой команды (CommandMeta на стороне сервера)."""
    return {
        "command_id": command_id or uuid.uuid4().hex,
        "actor": ADMIN_ACTOR,
        "reason": reason,
        "dry_run": False,  # True — только проверить, ничего не менять
    }


# ---------------------------------------------------------------------
# 1. ВЫДАЧА ЗВЁЗД
# ---------------------------------------------------------------------
# Эквивалент кнопки «Выдать звёзды» в админке
# (POST /api/actions/grant-stars -> Admin API /v1/accounts/grant-stars).
async def grant_stars(
    user_id: int,
    amount: int,
    reason: str = "Выдача звёзд ботом",
    command_id: str | None = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount должен быть > 0")

    # Здесь user_id и amount — обычные числа (не строки).
    return await _admin_request(
        "POST",
        "/v1/accounts/grant-stars",
        {
            **_command_meta(reason, command_id),
            "user_id": int(user_id),
            "amount": int(amount),
        },
    )


# ---------------------------------------------------------------------
# 2. ВЫДАЧА NFT-ЮЗЕРНЕЙМА (коллекционный юзернейм)
# ---------------------------------------------------------------------
# Создаёт коллекционный юзернейм сразу с владельцем owner_user_id.
# currency: "XTR" (звёзды), "TON" или "USD" — это лишь пометка о цене
# в карточке; реальных списаний сервер не делает. Для бесплатной выдачи
# оставьте amount=0.
# Имя должно соответствовать правилам юзернеймов и быть свободным.
async def mint_collectible_username(
    username: str,
    owner_user_id: int,
    currency: str = "XTR",
    amount: int = 0,
    reason: str = "Выдача NFT-юзернейма ботом",
    command_id: str | None = None,
) -> dict:
    username = username.strip().lstrip("@").lower()

    # ВНИМАНИЕ: тут сервер ждёт owner_user_id и amount СТРОКАМИ
    # (тег `json:",string"` в Go) — числом запрос будет отклонён.
    return await _admin_request(
        "POST",
        "/v1/collectible-usernames/mint",
        {
            **_command_meta(reason, command_id),
            "username": username,
            "owner_user_id": str(int(owner_user_id)),
            "currency": currency,
            "amount": str(int(amount)),
        },
    )


# Передать уже существующий (например, лежащий в «хранилище») юзернейм.
async def transfer_collectible_username(
    username: str,
    to_user_id: int,
    reason: str = "Передача NFT-юзернейма ботом",
    command_id: str | None = None,
) -> dict:
    return await _admin_request(
        "POST",
        "/v1/collectible-usernames/transfer",
        {
            **_command_meta(reason, command_id),
            "username": username.strip().lstrip("@").lower(),
            "to_user_id": str(int(to_user_id)),  # строкой
        },
    )


# Список коллекционных юзернеймов, которыми владеет пользователь.
async def list_user_collectible_usernames(user_id: int) -> dict:
    return await _admin_request(
        "GET",
        "/v1/collectible-usernames",
        params={"status": "owned", "owner_user_id": str(int(user_id))},
    )


# ---------------------------------------------------------------------
# 3. ВЫДАЧА ПОДАРКА / NFT-ПОДАРКА
# ---------------------------------------------------------------------
# Подарок уходит от официального системного аккаунта 777000, звёзды
# при этом не списываются.
#   upgrade=False — обычный подарок из каталога.
#   upgrade=True  — NFT (уникальный) подарок. Работает только если для
#                   gift_id в админке опубликованы коллекционные
#                   варианты (модели/узоры/фоны) и не исчерпан тираж.
#                   Атрибуты можно не указывать (0 — выбор по умолчанию
#                   на стороне сервера) или задать конкретные ID.
# Получатель — только пользователь; для NFT-подарка каналы не
# поддерживаются.
# gift_id смотрите в админке (каталог подарков) или через
# GET /v1/star-gift-catalog у Admin API.
async def give_gift(
    user_id: int,
    gift_id: int,
    upgrade: bool = False,
    message: str = "",
    hide_name: bool = False,
    model_attribute_id: int = 0,
    pattern_attribute_id: int = 0,
    backdrop_attribute_id: int = 0,
    reason: str = "Выдача подарка ботом",
    command_id: str | None = None,
) -> dict:
    if len(message) > 128:
        raise ValueError("message не длиннее 128 символов")

    # Все ID здесь тоже строками (`json:",string"` на сервере).
    return await _admin_request(
        "POST",
        "/v1/star-gift-catalog/give",
        {
            **_command_meta(reason, command_id),
            "sender_user_id": "0",  # 0 = официальный аккаунт 777000
            "user_id": str(int(user_id)),
            "channel_id": "0",
            "gift_id": str(int(gift_id)),
            "hide_name": hide_name,
            "message": message,
            "upgrade": upgrade,
            "model_attribute_id": str(int(model_attribute_id)),
            "pattern_attribute_id": str(int(pattern_attribute_id)),
            "backdrop_attribute_id": str(int(backdrop_attribute_id)),
        },
    )


# ---------------------------------------------------------------------
# 4. НОМЕРА, ПРИОБРЕТЁННЫЕ ПОЛЬЗОВАТЕЛЕМ
# ---------------------------------------------------------------------
# В этой сборке сервера НЕТ реестра коллекционных номеров (в коде
# fragment.getCollectibleInfo прямо сказано, что для телефонов реестра
# нет, а маршрутов mint-collectible-phone в Admin API не существует).
# Поэтому список купленных номеров берётся из базы БОТА по запросу
# PURCHASED_NUMBERS_SQL (см. настройки выше) — подправьте его под свою
# таблицу, где вы фиксируете покупки.
async def get_user_purchased_numbers(user_id: int) -> list[dict]:
    from sqlalchemy import text  # локальный импорт, чтобы не трогать шапку

    async with SessionLocal() as session:
        result = await session.execute(
            text(PURCHASED_NUMBERS_SQL),
            {"user_id": int(user_id)},
        )
        return [dict(row._mapping) for row in result]


# ---------------------------------------------------------------------
# 5. ВЫДАЧА НОМЕРА (ТОЛЬКО КОММЕНТАРИЙ — как сделать)
# ---------------------------------------------------------------------
# Реестра номеров нет, поэтому «выдать номер» = сменить пользователю
# логин-номер телефона. Admin API это умеет:
#
#     POST /v1/accounts/set-phone
#     {
#         "command_id": "...", "actor": "...", "reason": "...",
#         "user_id": 123456789,          # число
#         "phone": "88801234567"         # новый номер, только цифры
#     }
#
# Готовая функция (раскомментируйте, если нужно):
#
# async def assign_phone_number(user_id: int, phone: str,
#                               reason: str = "Выдача номера ботом",
#                               command_id: str | None = None) -> dict:
#     phone = re.sub(r"\D", "", phone)
#     return await _admin_request(
#         "POST",
#         "/v1/accounts/set-phone",
#         {
#             **_command_meta(reason, command_id),
#             "user_id": int(user_id),
#             "phone": phone,
#         },
#     )
#
# Нюансы:
#   * номер не должен быть занят другим аккаунтом (иначе ошибка
#     «phone number occupied»);
#   * номер с префиксом 888 (7–15 цифр) сервер принимает как виртуальный
#     логин без проверки по libphonenumber — удобно для «анонимных»
#     номеров;
#   * после смены номера в базе бота (Users.phone) его тоже нужно
#     обновить, иначе доставка кодов выше (поиск по Users.phone)
#     перестанет находить пользователя;
#   * запишите выдачу в свою таблицу покупок (см. п.4), чтобы
#     get_user_purchased_numbers() её показывал.


# ---------------------------------------------------------------------
# 6. НЕОБЯЗАТЕЛЬНЫЕ HTTP-ЭНДПОИНТЫ (для вызова из других сервисов)
# ---------------------------------------------------------------------
# Защищены той же схемой подписи, что и OTP-вебхук, но СВОИМ секретом
# ACTIONS_WEBHOOK_SECRET:
#     X-Telesrv-Timestamp: <unix-секунды>
#     X-Telesrv-Signature: sha256=hex(HMAC_SHA256(secret, ts + "." + body))
# Без секрета эндпоинты отвечают 503 и ничего не выдают.
#
#   POST /v1/actions/grant-stars     {"user_id":1,"amount":100}
#   POST /v1/actions/grant-username  {"user_id":1,"username":"vip"}
#   POST /v1/actions/give-gift       {"user_id":1,"gift_id":5,"upgrade":true}
#   GET  /v1/actions/numbers/{user_id}   (GET: подпись над пустым телом)
# Необязательное поле command_id в теле (или заголовок Idempotency-Key)
# защищает от двойной выдачи при повторе запроса.

async def _verify_actions_request(request: web.Request):
    """Проверяет подпись. Возвращает (payload, error_response)."""
    if not ACTIONS_SECRET:
        return None, web.json_response(
            {"error": "server_not_configured"}, status=503
        )

    raw_body = await request.read()
    timestamp = request.headers.get("X-Telesrv-Timestamp", "")
    signature = request.headers.get("X-Telesrv-Signature", "")

    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError):
        return None, web.json_response({"error": "invalid_timestamp"}, status=401)

    if abs(time.time() - timestamp_value) > MAX_SKEW_SECONDS:
        return None, web.json_response({"error": "expired_timestamp"}, status=401)

    expected = "sha256=" + hmac.new(
        ACTIONS_SECRET.encode(),
        timestamp.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return None, web.json_response({"error": "invalid_signature"}, status=401)

    if not raw_body:
        return {}, None

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, web.json_response({"error": "invalid_json"}, status=400)

    if not isinstance(payload, dict):
        return None, web.json_response({"error": "invalid_payload"}, status=400)

    return payload, None


def _admin_error_response(exc: AdminAPIError) -> web.Response:
    logger.error("Admin API call failed: %s", exc)
    status = exc.status if exc.status in (400, 404, 409) else 502
    return web.json_response(
        {"error": "admin_api_error", "details": exc.body}, status=status
    )


async def action_grant_stars(request: web.Request):
    payload, error = await _verify_actions_request(request)
    if error:
        return error
    try:
        result = await grant_stars(
            int(payload["user_id"]),
            int(payload["amount"]),
            reason=str(payload.get("reason") or "Выдача звёзд (HTTP)"),
            command_id=payload.get("command_id")
            or request.headers.get("Idempotency-Key"),
        )
    except (KeyError, TypeError, ValueError):
        return web.json_response({"error": "invalid_fields"}, status=400)
    except AdminAPIError as exc:
        return _admin_error_response(exc)
    return web.json_response(result)


async def action_grant_username(request: web.Request):
    payload, error = await _verify_actions_request(request)
    if error:
        return error
    try:
        result = await mint_collectible_username(
            str(payload["username"]),
            int(payload["user_id"]),
            currency=str(payload.get("currency") or "XTR"),
            amount=int(payload.get("amount") or 0),
            reason=str(payload.get("reason") or "Выдача NFT-юзернейма (HTTP)"),
            command_id=payload.get("command_id")
            or request.headers.get("Idempotency-Key"),
        )
    except (KeyError, TypeError, ValueError):
        return web.json_response({"error": "invalid_fields"}, status=400)
    except AdminAPIError as exc:
        return _admin_error_response(exc)
    return web.json_response(result)


async def action_give_gift(request: web.Request):
    payload, error = await _verify_actions_request(request)
    if error:
        return error
    try:
        result = await give_gift(
            int(payload["user_id"]),
            int(payload["gift_id"]),
            upgrade=bool(payload.get("upgrade", False)),
            message=str(payload.get("message") or ""),
            hide_name=bool(payload.get("hide_name", False)),
            model_attribute_id=int(payload.get("model_attribute_id") or 0),
            pattern_attribute_id=int(payload.get("pattern_attribute_id") or 0),
            backdrop_attribute_id=int(payload.get("backdrop_attribute_id") or 0),
            reason=str(payload.get("reason") or "Выдача подарка (HTTP)"),
            command_id=payload.get("command_id")
            or request.headers.get("Idempotency-Key"),
        )
    except (KeyError, TypeError, ValueError):
        return web.json_response({"error": "invalid_fields"}, status=400)
    except AdminAPIError as exc:
        return _admin_error_response(exc)
    return web.json_response(result)


async def action_user_numbers(request: web.Request):
    _, error = await _verify_actions_request(request)
    if error:
        return error
    try:
        user_id = int(request.match_info["user_id"])
    except ValueError:
        return web.json_response({"error": "invalid_user_id"}, status=400)

    try:
        numbers = await get_user_purchased_numbers(user_id)
    except Exception:
        logger.exception("Failed to load purchased numbers")
        return web.json_response({"error": "numbers_unavailable"}, status=500)

    return web.json_response({"user_id": user_id, "numbers": numbers}, dumps=lambda d: json.dumps(d, default=str))


def register_admin_routes(app: web.Application) -> web.Application:
    """Добавляет эндпоинты расширения в УЖЕ созданное приложение."""
    app.router.add_post("/v1/actions/grant-stars", action_grant_stars)
    app.router.add_post("/v1/actions/grant-username", action_grant_username)
    app.router.add_post("/v1/actions/give-gift", action_give_gift)
    app.router.add_get("/v1/actions/numbers/{user_id}", action_user_numbers)
    return app


def create_app_extended(bot: Bot) -> web.Application:
    """create_app (без изменений) + эндпоинты расширения."""
    return register_admin_routes(create_app(bot))


# =====================================================================
# Спасибо! Остальное допишете сами. Если что-то отвечает 400/403 от
# Admin API — смотрите поле "details" в ответе: сервер называет причину.
# =====================================================================
