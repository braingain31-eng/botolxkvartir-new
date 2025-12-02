from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils.keyboards import start_kb                     # ← ИСПРАВЛЕНО: убрал main_menu_kb
# from database.models import SessionLocal, User
from datetime import datetime
from database.firebase_db import create_or_update_user
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

class SearchStates(StatesGroup):
    waiting_query = State()
    waiting_sort = State()

WELCOME_TEXT = """
Добро пожаловать в **GoaNest Bot**!

Единая база жилья в Гоа:
1000+ объектов от **частников** (прямая цена + торг)
Виллы, бунгало, хостелы — всё в одном месте
Риэлторы тоже размещают у нас — **полный охват**
Обновление **каждый день**

Готов найти идеальное жильё?
"""

def is_saturday():
    from datetime import datetime
    return datetime.now().weekday() == 5  # 5 = суббота

def get_prices_in_stars():
    return 950, 1900  # пример цен в Stars

@router.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    create_or_update_user(user_id, user_type="client")
    await message.answer(WELCOME_TEXT, reply_markup=start_kb(), disable_web_page_preview=True)


@router.callback_query(F.data.in_(["pay_7", "pay_30"]))
async def show_payment_options(call: CallbackQuery):
    if is_saturday():
        stars_7, stars_30 = get_prices_in_stars()
        await call.message.edit_text(
            "Оплата через **Telegram Stars** (только по субботам, +5%):\n\n"
            f"7 дней — **{stars_7} Stars**\n"
            f"30 дней — **{stars_30} Stars**\n\n"
            "После оплаты — доступ активируется мгновенно.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("Оплатить 7 дней", callback_data="pay_7")],
                [InlineKeyboardButton("Оплатить 30 дней", callback_data="pay_30")],
                [InlineKeyboardButton("Назад", callback_data="back_to_search")]
            ])
        )
    else:
        await call.message.edit_text(
            "Оплатите доступ:\n\n"
            "**10$ — 7 дней**\n"
            "**20$ — 30 дней**\n\n"
            "Оплата через Stripe / Razorpay / USDT",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("10$ — 7 дней", callback_data="pay_7")],
                [InlineKeyboardButton("20$ — 30 дней", callback_data="pay_30")],
                [InlineKeyboardButton("Назад", callback_data="back_to_search")]
            ])
        )
    await call.answer()