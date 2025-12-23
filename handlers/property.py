# handlers/property.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.firebase_db import get_property_by_id, get_user_premium_info, is_favorite, add_favorite, remove_favorite
import logging
from aiogram.exceptions import TelegramBadRequest
from utils.keyboards import payment_menu_kb  
from handlers.start import show_profile_menu
from handlers.search import smart_search


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

    premium_info = get_user_premium_info(call.from_user.id)
    is_premium = premium_info["is_premium"]
    url = prop['olx_url'] if is_premium else "Купить премиум, чтобы увидеть ссылку"

    text = f"""
<b>{prop['title']}</b>

{prop['area']} • ₹{prop['price_day_inr']}

{url}
    """.strip()

    # Клавиатура
    kb = InlineKeyboardBuilder()
    
    if is_premium:
        kb.button(text="Открыть в OLX", url=prop['olx_url'])
    else:
        kb.button(text="Купить премиум", callback_data="pay_premium")

    # Проверяем, в избранном ли объект
    is_fav = is_favorite(call.from_user.id, prop_id)
    fav_text = "Убрать из избранного" if is_fav else "Сохранить в избранное"
    fav_data = f"remove_fav_{prop_id}" if is_fav else f"add_fav_{prop_id}"
    kb.button(text=fav_text, callback_data=fav_data)

    # kb.button(text="Назад", callback_data="back")

    kb.adjust(1)  # ← обязательно, если хочешь 100% столбик

    try:
        if call.message.photo or call.message.video:
            await call.message.edit_caption(
                caption=text,
                reply_markup=kb.as_markup()
            )
        else:
            await call.message.edit_text(
                text,
                reply_markup=kb.as_markup(),
                disable_web_page_preview=True
            )
    except TelegramBadRequest:
        # На всякий случай — отправляем новое сообщение
        await call.message.answer(
            text,
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )

# Обработчик для избранного
@router.callback_query(F.data.startswith("add_fav_"))
async def add_to_favorites(call: CallbackQuery):
    prop_id = call.data.split("_")[2]
    add_favorite(call.from_user.id, prop_id)
    await call.answer("Добавлено в избранное!", show_alert=True)
    await show_property_details(call)  # Обновляем клавиатуру (теперь "Убрать")

@router.callback_query(F.data.startswith("remove_fav_"))
async def remove_from_favorites(call: CallbackQuery):
    prop_id = call.data.split("_")[2]
    remove_favorite(call.from_user.id, prop_id)
    await call.answer("Убрано из избранного!", show_alert=True)
    await show_property_details(call)  # Обновляем клавиатуру (теперь "Сохранить")

@router.callback_query(F.data == "back_to_search")
async def back_to_search(call: CallbackQuery):
    await call.message.delete()  # или edit на предыдущее сообщение
    await call.answer()

@router.callback_query(F.data == "pay_premium")
async def pay_premium(call: CallbackQuery):
    # await call.message.answer(
    #     "**Выберите способ оплаты:**\n\n",
    #     reply_markup=payment_menu_kb(),
    #     parse_mode="Markdown"
    # )
    # await call.answer()
    try:
        if call.message.photo:
            await call.message.edit_caption(
                caption="Контакты доступны только премиум-пользователям\n\n"
                        "Оплати подписку — и увидишь номер и WhatsApp хозяина сразу!\n\n"
                        "Выбери способ:",
                reply_markup=payment_menu_kb()
            )
        else:
            await call.message.edit_text(
                "Контакты доступны только премиум-пользователям\n\n"
                "Оплати подписку — и увидишь номер и WhatsApp хозяина сразу!\n\n"
                "Выбери способ:",
                reply_markup=payment_menu_kb()
            )
    except:
        # Если не удалось — отправляем новое
        await call.message.answer(
            "Контакты доступны только премиум-пользователям\n\n"
            "Выбери подписку:",
            reply_markup=payment_menu_kb()
        )

    await call.answer("Требуется премиум", show_alert=True)

@router.callback_query(F.data.startswith("contact_"))
async def contact_handler(call: CallbackQuery):
    user_id = call.from_user.id

    # Используем полную инфу о премиуме
    premium_info = get_user_premium_info(user_id)

    if not premium_info["is_premium"]:
        # НЕ премиум — показываем красивое меню оплаты
        kb = payment_menu_kb()

        # await call.answer("Контакты доступны только премиум-пользователям", show_alert=True)
        # await call.message.answer(
        #     "Чтобы увидеть контакты хозяина — выбери подписку:\n"
        #     "Ты уже близко к лучшим вариантам",
        #     reply_markup=kb
        # )
        await call.message.answer(
                "Контакты доступны только премиум-пользователям\n\n"
                "Оплати подписку — и увидишь номер и WhatsApp хозяина сразу!\n\n"
                "Выбери удобный способ:",
                reply_markup=kb,
                reply_to_message_id=call.message.message_id  # ← КЛЮЧЕВОЕ!
            )
        await call.answer()  # отвечаем на callback
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

@router.callback_query(F.data == "top10")
async def cmd_top10(call: CallbackQuery):
    await smart_search(call.message, "топ-10 до $500")
    await call.answer()

@router.callback_query(F.data == "all_props")
async def cmd_all(call: CallbackQuery):
    await smart_search(call.message, "все варианты")
    await call.answer()

# @router.callback_query(F.data == "agent_menu")
# async def cmd_agent(call: CallbackQuery):
#     await call.message.answer("Риэлторское меню:", reply_markup=agent_menu_kb())
#     await call.answer()

@router.callback_query(F.data == "profile")
async def cmd_profile(call: CallbackQuery):
    await show_profile_menu(call.message)
    await call.answer()