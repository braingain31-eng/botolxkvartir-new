# handlers/property.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.firebase_db import get_property_by_id  # ← функция, которую надо создать
import logging
from aiogram.exceptions import TelegramBadRequest
from utils.keyboards import payment_menu_kb  

router = Router()

async def back_to_search(call):
    try:
        await call.message.delete()
    except TelegramBadRequest as e:
        # Игнорируем ошибки удаления сообщения
        if "message can't be deleted" in str(e):
            logger.debug("Не удалось удалить сообщение: оно больше не доступно для удаления")
        else:
            logger.error(f"Ошибка при удалении сообщения: {e}")
    
    # Продолжаем выполнение остальных действий
    # ...

async def show_property_details(call):
    try:
        await call.answer()
    except TelegramBadRequest as e:
        # Игнорируем ошибки с устаревшими callback-запросами
        if "query is too old" in str(e):
            logger.debug("Попытка ответить на устаревший callback-запрос")
            return
        else:
            logger.error(f"Ошибка при ответе на callback: {e}")

@router.callback_query(F.data.startswith("prop_"))
async def show_property_details(call: CallbackQuery):
    prop_id = call.data.split("_")[1]  # берём id после "prop_"

    prop = get_property_by_id(prop_id)
    if not prop:
        await call.answer("Объявление удалено или недоступно", show_alert=True)
        return

    text = f"""
<b>{prop['title']}</b>

{prop['area']} • ₹{prop['price_day_inr']}/день
Источник: OLX.in

{prop['olx_url']}
    """.strip()

    # Кнопка "Назад" — возвращает в поиск (опционально)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад", callback_data="back_to_search")
    kb.button(text="Открыть в OLX", url=prop['olx_url'])

    if prop.get('photos') and len(prop['photos']) > 1:
        # Если много фото — можно сделать галерею, но пока просто первое
        await call.message.edit_media(
            media=prop['photos'][0],
            reply_markup=kb.as_markup()
        )
        await call.message.edit_caption(caption=text, reply_markup=kb.as_markup())
    else:
        await call.message.edit_caption(caption=text, reply_markup=kb.as_markup())

    await call.answer()

@router.callback_query(F.data == "back_to_search")
async def back_to_search(call: CallbackQuery):
    await call.message.delete()  # или edit на предыдущее сообщение
    await call.answer()

@router.callback_query(F.data.startswith("contact_"))
async def contact_handler(call: CallbackQuery):
    user_id = call.from_user.id

    if not is_user_premium(user_id):
        # Пользователь НЕ премиум → показываем меню оплаты
        kb = payment_menu_kb()  # ← ТВОЁ КРАСИВОЕ МЕНЮ ИЗ keyboards.py
        
        await call.answer("Контакты хозяев — только для премиум-пользователей", show_alert=True)
        await call.message.answer(
            "Чтобы увидеть контакты — выбери подписку:",
            reply_markup=kb
        )
        return

    # Пользователь премиум → показываем контакты
    prop_id = call.data.split("_", 1)[1]  # надёжнее, чем split("_")[1]
    prop = get_property_by_id(prop_id)

    if not prop:
        await call.answer("Объект не найден или удалён", show_alert=True)
        return

    # Берём контакты (если нет — пишем, что скрыты)
    contacts = prop.get("contacts", "Контакты скрыты владельцем")
    owner_name = prop.get("owner_name", "Владелец")

    # Формируем красивое сообщение
    text = f"""
Контакты владельца:

{owner_name}
{contacts}

Напиши ему напрямую — торгуйся смело!
    """.strip()

    # Кнопка "Назад" — возвращаем в карточку объявления
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад к объявлению", callback_data=f"prop_{prop_id}")

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        disable_web_page_preview=True
    )
    await call.answer()