# handlers/property.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.firebase_db import get_property_by_id, get_user_premium_info
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

    # Используем полную инфу о премиуме
    premium_info = get_user_premium_info(user_id)

    if not premium_info["is_premium"]:
        # НЕ премиум — показываем красивое меню оплаты
        kb = payment_menu_kb()

        await call.answer("Контакты доступны только премиум-пользователям", show_alert=True)
        await call.message.answer(
            "Чтобы увидеть контакты хозяина — выбери подписку:\n"
            "Ты уже близко к лучшим вариантам",
            reply_markup=kb
        )
        return

    # Пользователь премиум — показываем контакты
    prop_id = call.data.split("_", 1)[1]
    prop = get_property_by_id(prop_id)

    if not prop:
        await call.answer("Объект удалён или недоступен", show_alert=True)
        return

    # Формируем красивое сообщение с контактами
    owner_name = prop.get("owner_name", "Владелец").strip()
    contacts = prop.get("contacts", "Контакты скрыты").strip()

    text = f"""
<b>Контакты владельца:</b>

{owner_name}
{contacts}

Напиши ему напрямую — торгуйся смело!
    """.strip()

    # Кнопка "Назад" — возвращаемся к карточке объявления
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад к объявлению", callback_data=f"prop_{prop_id}")

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        disable_web_page_preview=True
    )
    await call.answer()