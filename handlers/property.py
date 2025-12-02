# handlers/property.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.firebase_db import get_property_by_id  # ← функция, которую надо создать
import logging
from aiogram.exceptions import TelegramBadRequest

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