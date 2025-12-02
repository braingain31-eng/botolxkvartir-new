# handlers/payment_menu.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

@router.callback_query(F.data == "show_payment")
async def show_payment_menu(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    
    # Вариант 1: Карта
    builder.row(
        InlineKeyboardButton("Карта (Stripe)", callback_data="pay_card_7"),
        InlineKeyboardButton("Карта (Stripe)", callback_data="pay_card_30")
    )
    
    # Вариант 2: Крипта
    builder.row(
        InlineKeyboardButton("TON", callback_data="pay_crypto_7_ton"),
        InlineKeyboardButton("TON", callback_data="pay_crypto_30_ton")
    )
    builder.row(
        InlineKeyboardButton("USDT (TRC20)", callback_data="pay_crypto_7_usdt"),
        InlineKeyboardButton("USDT (TRC20)", callback_data="pay_crypto_30_usdt")
    )
    
    # Вариант 3: Stars
    builder.row(
        InlineKeyboardButton("1000 Stars", callback_data="pay_stars_7"),
        InlineKeyboardButton("2000 Stars", callback_data="pay_stars_30")
    )
    
    builder.row(InlineKeyboardButton("Назад", callback_data="back"))

    await call.message.edit_text(
        "**Выберите способ оплаты:**\n\n"
        "7 дней — доступ к контактам\n"
        "30 дней — полный премиум",
        reply_markup=builder.as_markup()
    )