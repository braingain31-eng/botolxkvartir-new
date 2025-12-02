# handlers/search.py — УМНЫЙ ПОИСК ЧЕРЕЗ GROK (НОЯБРЬ 2025)

from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.firebase_db import get_properties
from utils.grok_api import ask_grok
from utils.voice_handler import download_voice
from utils.voice_to_text import voice_to_text
import os
import aiohttp
import aiofiles
import hashlib
import json
import re

router = Router()
os.makedirs("cached_photos", exist_ok=True)


# === Голосовой ввод ===
@router.message(F.voice)
async def voice_search(message: Message):
    thinking = await message.answer("Распознаю голос...")
    file_path = await download_voice(message)
    if not file_path:
        return await thinking.edit_text("Ошибка загрузки голосового")

    text = await voice_to_text(file_path)
    if not text:
        return await thinking.edit_text("Не понял речь. Напишите текстом")

    await thinking.edit_text(f"Понял: \"{text}\"\nАнализирую запрос...")
    await smart_search(message, text)


# === Текстовый ввод ===
@router.message(F.text)
async def text_search(message: Message):
    if message.text.startswith("/"):
        return  # команды не трогаем
    await smart_search(message, message.text)


# === ГЛАВНЫЙ УМНЫЙ ПОИСК ===
async def smart_search(message: Message, user_query: str):
    # Шаг 1: Отправляем в Grok с промптом, который не требует обязательных уточнений
    grok_response = await ask_grok(f"""
    Ты — ассистент по поиску жилья в Гоа. Пользователь хочет найти подходящие варианты.

    Пользовательский запрос: "{user_query}"

    Проанализируй запрос и верни ТОЛЬКО JSON в следующем формате:

    {{
        "action": "search",
        "filters": {{
            "area": "Anjuna" | "Arpora" | "Vagator" | null,
            "price_day_inr__lte": 25000 | null,
            "price_day_inr__gte": 8000 | null,
            "bedrooms__gte": 1 | null,
            "guests__gte": 2 | null,
            "has_pool": true | false | null,
            "owner_type": "private" | null
        }},
        "sort": "price_asc" | "price_desc" | "newest" | null
    }}

    Правила:
    - Если запрос понятен и можно применить хотя бы один фильтр, используй action: "search"
    - НЕ требуй уточнений, если запрос достаточно ясен для поиска
    - Для запросов типа "дешевые варианты", "самые дешевые" или "всё что есть" установи разумные фильтры без уточнений:
    - price_day_inr__lte: 20000 или 25000
    - sort: "price_asc"
    - Если в запросе нет указания района, оставь area: null
    - Если не указано количество спален или гостей, оставь соответствующие фильтры null
    - Используй только те фильтры, которые явно следуют из запроса

    Не запрашивай уточнения, если запрос позволяет выполнить поиск. Предпочитай выполнение поиска с разумными предположениями, а не постоянные уточнения.
    """)

    # Шаг 2: Пытаемся распарсить JSON
    try:
        data = json.loads(grok_response.strip("```json").strip("```"))
        action = data.get("action", "search")
    except Exception as e:
        logger.error(f"Ошибка парсинга ответа Grok: {e}")
        # В случае ошибки выполняем поиск без фильтров, отсортированный по цене
        data = {
            "filters": {},
            "sort": "price_asc"
        }

    # Формируем фильтры и сортировку
    filters = {k: v for k, v in data.get("filters", {}).items() if v is not None}
    sort = data.get("sort")

    # Применяем сортировку
    order_by = None
    if sort == "price_asc":
        order_by = "price_day_inr"
    elif sort == "price_desc":
        order_by = "-price_day_inr"
    elif sort == "newest":
        order_by = "-created_at"

    # Выполняем поиск
    props = get_properties(filters=filters, order_by=order_by, limit=20)

    if not props:
        # Если ничего не найдено, пробуем поиск без фильтров
        props = get_properties(order_by="price_day_inr", limit=20)
        
        if props:
            await message.answer(
                "По указанным критериям ничего не найдено. Показываю доступные варианты, отсортированные по цене:"
            )
        else:
            await message.answer("На данный момент подходящих вариантов нет.")
            return

    await message.answer(f"Найдено {len(props)} вариантов:")
    await show_results(message, props)


# === Отправка карточек с кэшированием фото ===
async def show_results(message: Message, props: list):
    for p in props:
        title = p.get("title", "Жильё в Гоа")
        area = p.get("area", "Гоа")
        price_inr = p.get("price_day_inr", 0)
        guests = p.get("guests", 2)
        photo_url = p.get("photos", [None])[0]

        caption = f"<b>{title}</b>\n" \
                  f"{area} • ₹{price_inr}/сутки\n" \
                  f"до {guests} гостей"

        kb = InlineKeyboardBuilder()
        kb.button(text="Подробнее", callback_data=f"prop_{p.get('id')}")
        kb.button(text="Написать хозяину", callback_data=f"contact_{p.get('id')}")

        await send_cached_photo(message, photo_url, caption, kb.as_markup())

    await message.answer("Хотите больше вариантов — уточните запрос!")


# === Кэширование и отправка фото ===
async def send_cached_photo(message, photo_url: str, caption: str, reply_markup=None):
    if not photo_url:
        return await message.answer(f"{caption}\n\n(фото нет)", reply_markup=reply_markup)

    if photo_url.startswith(("AgAC", "BAAC")):
        return await message.answer_photo(photo_url, caption=caption, reply_markup=reply_markup)

    file_hash = hashlib.md5(photo_url.encode()).hexdigest()
    file_path = f"cached_photos/{file_hash}.jpg"

    if os.path.exists(file_path):
        return await message.answer_photo(FSInputFile(file_path), caption=caption, reply_markup=reply_markup)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(data)
                    await message.answer_photo(FSInputFile(file_path), caption=caption, reply_markup=reply_markup)
                    return
    except:
        pass

    await message.answer(f"{caption}\n\nФото: {photo_url}", reply_markup=reply_markup, disable_web_page_preview=False)