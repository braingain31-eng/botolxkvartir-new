from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.keyboards import start_kb, payment_menu_kb, main_menu_inline                    # ← ИСПРАВЛЕНО: убрал main_menu_kb
# from database.models import SessionLocal, User
from datetime import datetime
from handlers.search import show_results
from database.firebase_db import create_or_update_user, get_user_premium_info, get_user, get_property_by_id
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

class SearchStates(StatesGroup):
    waiting_query = State()
    waiting_sort = State()

WELCOME_TEXT = """
@GoaNestBot — самый честный и умный поиск жилья в Гоа 

Зачем он нужен:

1. Видишь ВСЁ, что есть на рынке.
Никаких «секретных» вариантов и скрытых объявлений — доступна полная база.

2. Экономишь до 50%.
Тысячи объектов напрямую от владельцев — без риэлторской наценки.

3. Получаешь контакты хозяина.
Пишешь напрямую и торгуешься. Совет от нас: смело проси −20% от указанной цены — почти всегда работает.

4. Даже в бесплатной версии:
- мгновенные уведомления о новых вариантах;
- всегда актуальные цены, без наценок риэлторов.

5. Бот постоянно обновляет поиск по всем базам.
Пришлёт тебе новую квартиру одним из первых — идеально для арендаторов.
А если ты риэлтор — ещё лучше: бот существенно экономит время.

Просто напиши голосом или текстом, что ищешь — остальное мы сделаем сами.
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

    # Одно красивое сообщение + inline-меню под ним
    await message.answer(
        WELCOME_TEXT + "\n\nВыбери, что хочешь:",
        reply_markup=main_menu_inline(),  # ← главное меню под сообщением
        disable_web_page_preview=True
    )

    # А постоянное меню внизу (start_kb) — оно и так остаётся от предыдущих запусков
    # Если его нет — можно принудительно показать:
    await message.answer("Главное меню всегда здесь:", reply_markup=start_kb())

# @router.message(F.text == "Профиль")
# async def show_profile_menu(message: Message):
#     user_id = message.from_user.id
#     name = message.from_user.full_name or "Гость"
#     info = get_user_premium_info(user_id)

#     if info["is_premium"]:
#         text = f"""
# Привет, <b>{name}</b>!

# Твой статус: <b>Премиум активен</b>
# Осталось: <b>{info['days_left']} дн.</b>
# Истекает: <code>{info['expires_at'][:10]}</code>

# Ты уже в элите
#         """
#         kb = InlineKeyboardBuilder()
#         kb.button(text="Назад в меню", callback_data="back_to_main")
#         reply_markup = kb.as_markup()  # ← Здесь можно, потому что kb — Builder
#     else:
#         text = f"""
# Привет, <b>{name}</b>!

# Сейчас ты на стандартной версии

# Хочешь контакты хозяев и приоритет в поиске?

# Выбери удобный способ оплаты:
#         """
#         reply_markup = payment_menu_kb()  # ← Прямо функция, без .as_markup()

#     await message.answer(
#         text.strip(),
#         reply_markup=reply_markup,
#         disable_web_page_preview=True
#     )

@router.message(F.text == "Новый поиск")
@router.callback_query(F.data == "new_search")
async def realtor_entry_handler(event: Message | CallbackQuery):
    await new_search(event)

async def new_search(event):

    # Определяем user_id и тип события
    if isinstance(event, Message):
        user_id = event.from_user.id
        send_method = event.answer
    else:  # CallbackQuery
        user_id = event.from_user.id
        send_method = event.message.edit_text
        await event.answer()  

    kb = InlineKeyboardBuilder()
    kb.button(text="Поиск текстом", callback_data="search_text")
    kb.button(text="Поиск голосом", callback_data="search_voice")
    kb.adjust(1)

    text = (
        "Новый поиск в GoaNest Bot\n\n"
        "Как работает поиск:\n"
        "• Произвольный запрос: Напиши текстом, что ищешь (тип жилья, бюджет, район, даты, кол-во человек).\n"
        "• Голосовой поиск: Доступен с премиум-подпиской — говори, и ИИ обработает.\n"
        "В базе: 20% объектов от владельцев (прямая аренда, торг), 80% от риэлторов (профессиональные варианты).\n\n"
    )

    await send_method(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "search_text")
async def search_text(call: CallbackQuery):

    text = (
        "Поиск текстом\n\n"
        "Инструкция:\n"
        "Напиши запрос в свободной форме.\n"
        "Укажи:\n"
        "• Тип жилья (вилла, бунгало, квартира)\n"
        "• Бюджет (например, до 3000 ₿/ночь)\n"  
        "• Район (Анжуна, Арпора и т.д.)\n"
        "• Даты (с 15 декабря на неделю)\n"      
        "• Кол-во человек (на 4 гостей)\n"
        "• Дополнительно (бассейн, Wi-Fi, вид на море)\n"
        "Пример: _Вилла на 4 человека, до 3000 ₿/ночь, в Анжуне, с 15 декабря на неделю, с бассейном\n\n"
    )

    await call.answer(text)

@router.callback_query(F.data == "search_voice")
async def search_voice(call: CallbackQuery):

    text = (
        "Поиск голосом\n\n"
        "Голосовой поиск доступен только с премиум-подпиской!\n"
        "Премиум даёт:\n"
        "• Все контакты: Риэлторов и владельцев — бронь напрямую, без посредников.\n"
        "• Голосовой поиск: Говори запрос — ИИ уточнит и найдёт.\n"  
        "• Рассылка новых вариантов: Автоматически получай уведомления о подходящих объектах в реальном времени.\n"
        "• Другие функции: Приоритет в выдаче, статистика просмотров (если риэлтор).\n\n"      
    )

    await call.answer(text, reply_markup=payment_menu_kb())


@router.message(F.text == "Профиль")
async def show_profile_menu(message: Message):
    user_id = message.from_user.id
    name = message.from_user.full_name or "Гость"
    info = get_user_premium_info(user_id)

    # === Получаем избранное (работает для всех!) ===
    user = get_user(user_id)
    favorite_ids = user.get("favorites", []) if user else []

    # === Статус премиума ===
    if info["is_premium"]:
        premium_text = f"""
<b>Премиум активен</b>
Осталось: <b>{info['days_left']} дн.</b>
Истекает: <code>{info['expires_at'][:10]}</code>

Ты уже в элите
        """
    else:
        premium_text = """
<b>Стандартная версия</b>

Хочешь:
• Контакты хозяев
• Приоритет в поиске

→ Выбери подписку ниже
        """

    # === ИЗБРАННОЕ — ВСЕГДА ДОСТУПНО ===
    if not favorite_ids:
        favorites_text = "<i>В избранном пока ничего нет</i>"
    else:
        favorites_text = f"<b>Избранное ({len(favorite_ids)}):</b>"

    # === Клавиатура ===
    kb = InlineKeyboardBuilder()

    if favorite_ids:
        kb.button(text="Очистить избранное", callback_data="clear_favorites")

    if not info["is_premium"]:
        kb.button(text="1000 Stars → 7 дней", callback_data="pay_stars_7")
        kb.button(text="2000 Stars → 30 дней", callback_data="pay_stars_30")

    # kb.button(text="Назад в меню", callback_data="back_to_main")

    kb.adjust(1)  # ← обязательно, если хочешь 100% столбик

    # === Отправляем профиль ===
    text = f"""
Привет, <b>{name}</b>!

{premium_text}

{favorites_text}
    """.strip()

    await message.answer(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # # === Если есть избранное — показываем объекты ===
    # if favorite_ids:
    #     props = []
    #     for prop_id in favorite_ids[:20]:  # лимит 20
    #         prop = get_property_by_id(prop_id)
    #         if prop:
    #             props.append(prop)

    #     if props:
    #         await message.answer("Твоё избранное:")
    #         await show_results(message, props)
    #     else:
    #         await message.answer("Некоторые объекты из избранного были удалены")

@router.message(F.text == "Избранное")  # ← Исправлено: правильное написание
async def show_izbranoe(message: Message):
    user_id = message.from_user.id
    name = message.from_user.full_name or "Гость"

    # Получаем данные пользователя
    user = get_user(user_id)
    favorite_ids = user.get("favorites", []) if user else []

    # Собираем объекты избранного
    props = []
    removed_count = 0
    for prop_id in favorite_ids[:30]:  # чуть больше, на всякий случай
        prop = get_property_by_id(prop_id)
        if prop and prop.get("status") == "active":  # только активные
            props.append(prop)
        else:
            removed_count += 1

    # === Текст ===
    if not props:
        text = """
<b>Избранное пустое</b> 😔

Добавляй понравившиеся виллы в избранное — они появятся здесь!

Вернись в поиск и найди что-то крутое ❤️
        """.strip()
        
        # Кнопки нет — смысла очищать пустое нет
        kb = None
    else:
        count = len(props)
        text = f"""
<b>Твоё избранное ({count})</b> ❤️

Вот что ты сохранил:
        """.strip()

        # Клавиатура с очисткой
        kb = InlineKeyboardBuilder()
        kb.button(text="Очистить избранное", callback_data="clear_favorites")
        kb.adjust(1)
        reply_markup = kb.as_markup()
    # === Отправляем всё одним сообщением + карточки ===
    await message.answer(
        text,
        reply_markup=reply_markup if props else None,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # Показываем объекты (если есть)
    if props:
        await show_results(message, props)

    # Уведомляем, если что-то удалено
    if removed_count > 0:
        await message.answer(f"ℹ️ {removed_count} объект(а) из избранного были удалены хозяином")

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

# === Обработка кнопки "Очистить избранное" ===
@router.callback_query(F.data == "clear_favorites")
async def clear_favorites_confirm(call: CallbackQuery):
    user_id = call.from_user.id
    user = get_user(user_id)
    favorite_ids = user.get("favorites", []) if user else []

    if not favorite_ids:
        await call.answer("Избранное уже пустое", show_alert=True)
        return

    # Клавиатура с подтверждением
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, очистить всё", callback_data="confirm_clear_fav")
    kb.button(text="Отмена", callback_data="cancel_clear_fav")
    kb.adjust(1)

    await call.message.edit_reply_markup(reply_markup=kb.as_markup())
    await call.answer("Ты уверен?")


# === Подтверждение очистки ===
@router.callback_query(F.data == "confirm_clear_fav")
async def confirm_clear_favorites(call: CallbackQuery):
    user_id = call.from_user.id
    
    # ОЧИЩАЕМ избранное в базе
    create_or_update_user(user_id, favorites=[])

    # Перерисовываем профиль заново
    await show_profile_menu(call.message)
    
    await call.answer("Избранное очищено!", show_alert=True)


# === Отмена очистки ===
@router.callback_query(F.data == "cancel_clear_fav")
async def cancel_clear_favorites(call: CallbackQuery):
    # Просто возвращаем исходную клавиатуру профиля
    await show_profile_menu(call.message)
    await call.answer("Отменено")
