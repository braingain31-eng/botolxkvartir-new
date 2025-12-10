from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils.keyboards import start_kb, payment_menu_kb                     # ← ИСПРАВЛЕНО: убрал main_menu_kb
# from database.models import SessionLocal, User
from datetime import datetime
from database.firebase_db import create_or_update_user
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

class SearchStates(StatesGroup):
    waiting_query = State()
    waiting_sort = State()

WELCOME_TEXT = """
@GoaNestBot — самый честный и умный поиск жилья в Гоа 

Зачем он нужен:

1. Видишь ВСЁ, что есть на рынке  
   Никаких «секретных» вариантов и скрытых объявлений — 100% база

2. Экономишь до 50%  
   Тысячи объектов напрямую от владельцев — без риэлторской наценки

3. Получаешь контакты хозяина  
   Пишешь сам и торгуешься. Совет от нас: смело проси −20% от указанной цены — почти всегда прокатывает 

4. Даже в бесплатной версии  
   - Уведомления о новых вариантах мгновенно  
   - Всегда знаешь актуальные цены (чтобы риэлтор не наёб… не обманул тебя по цене)

5. Ничего не упустишь  
   Пока ты спишь — мы следим за свежими объявлениями и пингуем тебя первыми

Просто напиши голосом или текстом, что ищешь — остальное сделаем мы  
t.me/GoaNestBot
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


@router.message(F.text == "Профиль")
async def show_profile_menu(message: Message):
    user_id = message.from_user.id
    name = message.from_user.full_name or "Гость"
    info = get_user_premium_info(user_id)

    if info["is_premium"]:
        text = f"""
<b>Привет, {name}!</b>

Твой статус: <b>Премиум активен</b>
Осталось: <b>{info['days_left']} дн.</b>
Истекает: <code>{info['expires_at'][:10]}</code>

Ты уже в элите
        """
        kb = InlineKeyboardBuilder()
        kb.button(text="Назад в меню", callback_data="back_to_main")
    else:
        text = f"""
<b>Привет, {name}!</b>

Сейчас ты на стандартной версии

Хочешь:
• Контакты хозяев
• Приоритет в поиске
• Новые объекты первым

Выбери удобный способ оплаты:
        """
        kb = payment_menu_kb()  # ← ВОТ ТВОЁ ГОТОВОЕ МЕНЮ!

    await message.answer(
        text.strip(),
        reply_markup=kb.as_markup(),
        disable_web_page_preview=True
    )

# Возврат в главное меню
@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=start_kb()
    )
    await call.answer()

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