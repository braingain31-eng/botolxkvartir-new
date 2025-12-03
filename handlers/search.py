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
import logging

logger = logging.getLogger(__name__)

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
    thinking_msg = await message.answer("Думаю...")

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

    Если запрос понятен — делай поиск. Если нет конкретики — ставь разумные значения (например, price до 25000 и sort по цене).
    Не пиши ничего кроме JSON..
    """)

    # --- САМЫЙ ЖЁСТКИЙ ПАРСЕР В МИРЕ ---
    json_str = grok_response.strip()
    json_str = re.sub(r"^```json\s*", "", json_str, flags=re.IGNORECASE)
    json_str = re.sub(r"```$", "", json_str).strip()

    try:
        data = json.loads(json_str)
    except Exception as e:
        logger.warning(f"Grok вернул невалидный JSON, используем дефолт. Ошибка: {e}\nОтвет был: {grok_response[:300]}")
        data = {"action": "search", "filters": {}, "sort": "price_asc"}

    await thinking_msg.delete()

    filters = {k: v for k, v in data.get("filters", {}).items() if v is not None}
    sort = data.get("sort", "price_asc")

    # Превращаем sort в order_by для Firebase
    order_by = {
        "price_asc": "price_day_inr",
        "price_desc": "-price_day_inr",
        "newest": "-created_at"
    }.get(sort, "price_day_inr")

    # Основной поиск
    props = get_properties(filters=filters, order_by=order_by, limit=20)

    # Если ничего — ищем вообще всё
    if not props:
        props = get_properties(order_by="price_day_inr", limit=20)
        if props:
            await message.answer("По твоим критериям ничего не нашёл.\nВот что есть прямо сейчас (по возрастанию цены):")
        else:
            await message.answer("Пока нет ни одного варианта в базе 😔\nСкоро будут!")
            return
    else:
        count_text = f"Найдено {len(props)} вариант{'ов' if len(props) > 1 else ''}"
        if filters:
            await message.answer(f"{count_text} по твоему запросу:")
        else:
            await message.answer(f"{count_text} (все доступные):")

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