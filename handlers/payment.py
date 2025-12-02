# handlers/payment.py
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    PreCheckoutQuery,
    Message,
    ContentType,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from datetime import datetime, timedelta

import config
from database.firebase_db import get_user, create_or_update_user, update_paid_until
from utils.keyboards import payment_menu_kb

router = Router()


# === FSM для ожидания скриншота крипто-оплаты ===
class CryptoPaymentStates(StatesGroup):
    waiting_proof = State()


# === Меню выбора способа оплаты ===
@router.callback_query(F.data == "show_payment")
async def show_payment_menu(call: CallbackQuery):
    await call.message.edit_text(
        "Выберите способ оплаты:\n\n"
        "• 7 дней — $10\n"
        "• 30 дней — $20",
        reply_markup=payment_menu_kb()
    )


# === 1. Оплата картой (Stripe/Razorpay) ===
@router.callback_query(F.data.startswith("pay_card_"))
async def pay_with_card(call: CallbackQuery):
    days = 7 if "7" in call.data else 30
    amount_cents = 1000 if days == 7 else 2000  # $10 → 1000 cents, $20 → 2000

    await call.message.answer_invoice(
        title=f"Премиум-доступ на {days} дней",
        description="Прямые контакты хозяев + приоритет в поиске",
        payload=f"{call.from_user.id}_{days}_card",
        provider_token=config.STRIPE_TOKEN or "YOUR_STRIPE_OR_RAZORPAY_TOKEN",  # ← в .env
        currency="USD",
        prices=[{"label": f"Премиум на {days} дней", "amount": amount_cents}],
        start_parameter="goanest-premium",
    )


# === 2. Оплата криптовалютой (TON / USDT) ===
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_with_crypto(call: CallbackQuery):
    days = 7 if "7" in call.data else 30
    crypto = "TON" if "ton" in call.data else "USDT_TRC20"
    wallet = config.CRYPTO_WALLETS[crypto]
    amount = 10 if days == 7 else 20

    kb = InlineKeyboardBuilder()
    kb.button(text="Я оплатил — прикрепить скриншот", callback_data=f"crypto_paid_{days}_{crypto}")

    await call.message.edit_text(
        f"Оплата криптовалютой ({crypto})\n\n"
        f"Сумма: <b>${amount}</b>\n"
        f"Кошелёк: <code>{wallet}</code>\n\n"
        "После перевода нажмите кнопку ниже и прикрепите скриншот транзакции.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("crypto_paid_"))
async def crypto_wait_proof(call: CallbackQuery, state: FSMContext):
    _, _, days_str, crypto = call.data.split("_")
    days = int(days_str)

    await state.update_data(
        user_id=call.from_user.id,
        days=days,
        crypto=crypto
    )
    await call.message.edit_text(
        "Пришлите скриншот транзакции (фото)\n"
        "Администратор проверит в течение 1 часа."
    )
    await state.set_state(CryptoPaymentStates.waiting_proof)


@router.message(F.photo, CryptoPaymentStates.waiting_proof)
async def receive_crypto_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    photo = message.photo[-1].file_id

    # Уведомляем админа
    admin_text = (
        f"НОВАЯ ОПЛАТА КРИПТОЙ\n\n"
        f"Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Сумма: <b>${10 if data['days']==7 else 20}</b>\n"
        f"Кошелёк: {data['crypto']}\n"
        f"Дата: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    )
    await message.bot.send_photo(config.ADMIN_ID, photo, caption=admin_text, parse_mode="HTML")

    await message.answer("Скриншот получен! Ожидайте активации (до 1 часа).")
    await state.clear()


# === 3. Оплата Telegram Stars ===
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_with_stars(call: CallbackQuery):
    days = 7 if "7" in call.data else 30
    stars_amount = config.WEEK_PRICE_STARS if days == 7 else config.MONTH_PRICE_STARS

    await call.message.answer_invoice(
        title=f"Премиум на {days} дней",
        description="Оплата через Telegram Stars",
        payload=f"{call.from_user.id}_{days}_stars",
        provider_token="",  # Stars не требует токена
        currency="XTR",
        prices=[{"label": f"Доступ на {days} дней", "amount": stars_amount}],
        start_parameter="goanest-stars",
    )


# === Общие обработчики ===
@router.pre_checkout_query()
async def pre_checkout(pcq: PreCheckoutQuery):
    await pcq.answer(ok=True)


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    user_id = int(parts[0])
    days = int(parts[1])
    method = parts[2] if len(parts) > 2 else "unknown"

    # Активируем премиум в Firebase
    update_paid_until(user_id, days)

    method_names = {
        "card": "картой (Stripe)",
        "stars": "Telegram Stars",
        "crypto": "криптовалютой (ожидается проверка)"
    }

    await message.answer(
        f"ОПЛАТА ПРОШЛА УСПЕШНО!\n\n"
        f"Доступ активирован на <b>{days} дней</b>\n"
        f"Способ: <b>{method_names.get(method, method)}</b>\n\n"
        f"Теперь вы видите все контакты хозяев!",
        parse_mode="HTML"
    )