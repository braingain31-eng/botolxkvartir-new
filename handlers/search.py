# handlers/search.py — УМНЫЙ ПОИСК ЧЕРЕЗ GROK (НОЯБРЬ 2025)

from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
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

# Список северных деревень по умолчанию
NORTH_GOA_DEFAULT_AREAS = [
    "Arambol", "Morjim", "Mandrem", "Siolim", "Kerim", "Querim",
    "Corgao", "Korgaon", "Ashvem", "Paliem", "Agarvada"
]


# === Голосовой ввод ===
@router.message(F.voice)
async def voice_search(message: Message):
    thinking = await message.answer("Распознаю голос...")
    file_path = await download_voice(message)
    if not file_path:
        return await thinking.edit_text("Ошибка загрузки голосового")

    text = await voice_to_text(file_path, file_id=message.voice.file_id)
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

@router.callback_query(lambda c: c.data and c.data.startswith("more_"))
async def show_more_properties(call: CallbackQuery):
    try:
        offset = int(call.data.split("_")[1])
    except:
        await call.answer("Ошибка", show_alert=True)
        return

    # Получаем кэшированные объявления
    remaining_props = getattr(call.bot, "search_cache", {}).get(call.from_user.id, [])
    
    if not remaining_props:
        await call.message.edit_text("Больше вариантов нет")
        await call.answer()
        return

    next_chunk = remaining_props[:10]
    new_offset = offset + 10

    # Отправляем следующий чанк
    for i, p in enumerate(next_chunk, start=offset + 1):
        await _send_property_card(call.message, p, i)

    # Обновляем кэш
    call.bot.search_cache[call.from_user.id] = remaining_props[10:]

    # Кнопка "Ещё", если остались
    still_more = len(call.bot.search_cache.get(call.from_user.id, []))
    if still_more > 0:
        kb = InlineKeyboardBuilder()
        kb.button(
            text=f"Ещё {min(still_more, 10)} из {still_more} ",
            callback_data=f"more_{new_offset}"
        )
        await call.message.answer("Есть ещё интересные варианты!", reply_markup=kb.as_markup())
    else:
        await call.message.answer("Это всё! Больше нет вариантов по вашему запросу")
        # Очищаем кэш
        if call.from_user.id in call.bot.search_cache:
            del call.bot.search_cache[call.from_user.id]

    await call.answer()

# === ГЛАВНЫЙ УМНЫЙ ПОИСК ===
async def smart_search(message: Message, user_query: str):
    thinking = await message.answer("Ищу лучшие варианты...")
    
    # Формируем строку со всеми районами для промпта
    areas_list = " | ".join([f'"{area}"' for area in NORTH_GOA_DEFAULT_AREAS])

    # Шаг 1: Формируем промпт для Grok с поддержкой количества
    prompt = f"""
    Ты — ассистент по поиску жилья ТОЛЬКО в Северном Гоа.
    Доступные районы (ОБЯЗАТЕЛЬНО выбирай только из них): {areas_str}

    Пользователь написал: "{user_query}"

    Твоя задача — вернуть ТОЛЬКО чистый JSON в формате:

    {{
    "action": "search",
    "filters": {{
        "area": "Arambol" | "Morjim" | ["Arambol", "Morjim"] | null,
        "price_day_inr__lte": 25000 | null,
        "price_day_inr__gte": 8000 | null,
        "bedrooms__gte": 1 | null,
        "guests__gte": 2 | null,
        "has_pool": true | false | null,
        "owner_type": "private" | "agent" | null
    }},
    "sort": "price_asc" | "price_desc" | "newest" | null,
    "limit": 10 | null
    }}

    ЖЁСТКИЕ ПРАВИЛА:
    1. Поле "area" может быть:
    - строкой: "Arambol" — если указан один район
    - массивом: ["Arambol", "Morjim"] — если указано несколько районов
    - null — если район не из списка выше
    2 Поддерживай все варианты написания:
    арамбол, арамболе, arambol, morjim, морджим, мандрем, мандрем, ашвем, вагатор, анжуна и т.д.
    3 Если пользователь написал "арамбол и морджим", "анжуна или вагатор", "в арамболе или рядом" — верни массив из этих районов
    4 Если пользователь сказал "любой район", "где угодно", "по всему северу" — поставь null
    5 Если запрос про долгосрок ("на месяц", "месяц и более", "долгосрочно") — ставь price_day_inr__lte: 2000–2500
    6 НИКОГДА не придумывай свои районы — только из списка: {areas_str}
    7. Если сказано "самые дешевые", "дешево", "бюджетно" — sort: "price_asc"
    8. Если сказано "новые", "недавно добавленные" — sort: "newest"
    9. Если указано количество ("5 вариантов", "покажи 3") — поставь в limit это число
    10. НИКОГДА не пиши пояснения — только JSON
    """
    logger.info(f"Отправляем промпт в Grok: {prompt[:500]}...")  # Лог запроса (первые 500 символов)

    grok_response = await ask_grok(prompt)

    logger.info(f"Получен ответ от Grok: {grok_response[:900]}...")  # Лог ответа (первые 500 символов)

    # Шаг 2: Парсинг JSON
    json_str = grok_response.strip()
    json_str = re.sub(r"^```json\s*", "", json_str, flags=re.IGNORECASE)
    json_str = re.sub(r"```$", "", json_str).strip()

    try:
        data = json.loads(json_str)
    except Exception as e:
        logger.warning(f"Grok вернул невалидный JSON, используем дефолт. Ошибка: {e}\nОтвет был: {grok_response[:300]}")
        data = {"action": "search", "filters": {}, "sort": "price_asc", "limit": null}

    await thinking.delete()

    filters = {k: v for k, v in data.get("filters", {}).items() if v is not None}

    raw_area = data.get("filters", {}).get("area")

    if raw_area:
        # Приводим к единому виду: всегда список
        if isinstance(raw_area, str):
            selected_areas = [raw_area]
        elif isinstance(raw_area, list):
            selected_areas = raw_area
        else:
            selected_areas = []
        
        # Фильтруем только валидные районы из нашего списка
        valid_areas = [a for a in selected_areas if a in NORTH_GOA_DEFAULT_AREAS]
        
        if valid_areas:
            filters["area__in"] = valid_areas
            logger.info(f"Grok выбрал районы: {valid_areas}")
        else:
            filters.pop("area", None)
    else:
        # Если Grok не указал район — можно добавить дефолт по всему северу
        filters["area__in"] = NORTH_GOA_DEFAULT_AREAS

    sort = data.get("sort", "price_asc")
    limit = data.get("limit", 20)  # Если limit от Grok null — 20 по умолчанию

    # Превращаем sort в order_by для Firebase
    order_by = {
        "price_asc": "price_day_inr",
        "price_desc": "-price_day_inr",
        "newest": "-created_at"
    }.get(sort, "price_day_inr")

    # Основной поиск
    props = get_properties(filters=filters, order_by=order_by, limit=limit)

    # Если ничего — ищем вообще всё
    if not props:
        props = get_properties(order_by="price_day_inr", limit=limit)
        if props:
            await message.answer("По твоим критериям ничего не нашёл.\nВот что есть прямо сейчас (по возрастанию цены):")
        else:
            await message.answer("Пока нет ни одного варианта в базе 😔\nСкоро будут!")
            return
    else:
        count_text = f"Нашёл {len(props)} подходящих вариант{'ов' if len(props) > 1 else ''}"
        if filters:
           await message.answer(
                f"{count_text}.\n\n"
                "Сначала покажу самые точные по твоему запросу\n"
                "Потом всё остальное — по убыванию релевантности\n\n"
                "Не переживай — ничего не спрятано\n"
                "Просто чтобы ты сразу увидел лучшее ❤️"
            )
        else:
            await message.answer(f"{count_text} (все доступные):")

    await show_results(message, props)


# # === Отправка карточек с кэшированием фото ===
# async def show_results(message: Message, props: list):
#     for index, p in enumerate(props, start=1):
#         title = p.get("title", "Жильё в Гоа")
#         area = p.get("area", "Гоа")
#         price_inr = p.get("price_day_inr", 0)
#         guests = p.get("guests", 2)
#         photo_url = p.get("photos", [None])[0]

#         caption = f"<b>{title}</b>\n" \
#                   f"{area} • ₹{price_inr}/сутки\n" \
#                   f"до {guests} гостей"

#         kb = InlineKeyboardBuilder()
#         kb.button(text="Подробнее", callback_data=f"prop_{p.get('id')}")
#         kb.button(text="Написать хозяину", callback_data=f"contact_{p.get('id')}")

#         await send_cached_photo(message, photo_url, caption, kb.as_markup())

#         if index == 10 and len(props) > 10:
#             await message.answer(
#                 "Ты уже прошёл топ-10 самых подходящих\n"
#                 "Дальше идут хорошие, но чуть менее точные\n"
#                 "Всё честно и по делу"
#             )

    # await message.answer("Хотите больше вариантов — уточните запрос!")

async def show_results(message: Message, props: list):
    if not props:
        await message.answer("Ничего не найдено. Попробуйте изменить запрос.")
        return

    total = len(props)
    chunk_size = 10

    # Отправляем первые 10
    for i, p in enumerate(props[:chunk_size], start=1):
        await _send_property_card(message, p, i)

    # Если объявлений больше 10 — показываем кнопку "Ещё"
    if total > chunk_size:
        remaining = total - chunk_size
        kb = InlineKeyboardBuilder()
        kb.button(
            text=f"Показать ещё {min(remaining, chunk_size)} из {remaining} ",
            callback_data=f"more_{chunk_size}"  # начало следующего чанка
        )
        await message.answer(
            "Это только начало!\n"
            "Я нашёл ещё варианты — хочешь посмотреть?",
            reply_markup=kb.as_markup()
        )
    else:
        await message.answer("Это все доступные варианты на данный момент\nХочешь другой поиск — просто напиши")

    # Сохраняем оставшиеся объявления в состояние пользователя
    if total > chunk_size:
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Если используешь FSMContext — передавай его в функцию
        # Здесь пример с простым кэшем в памяти (для примера)
        if not hasattr(message.bot, "search_cache"):
            message.bot.search_cache = {}
        message.bot.search_cache[message.from_user.id] = props[chunk_size:]

async def _send_property_card(message_or_call, prop: dict, number: int):
    title = prop.get("title", "Жильё в Гоа")
    area = prop.get("area", "Гоа")
    price_inr = prop.get("price_day_inr", 0)
    guests = prop.get("guests", 2)
    photo_url = prop.get("photos", [None])[0]

    caption = f"<b>{number}. {title}</b>\n" \
              f"{area} • ₹{price_inr:,}\n" \
              f"до {guests} гостей".replace(",", " ")

    kb = InlineKeyboardBuilder()
    kb.button(text="Подробнее", callback_data=f"prop_{prop.get('id')}")
    kb.button(text="Написать хозяину", callback_data=f"contact_{prop.get('id')}")

    if isinstance(message_or_call, Message):
        await send_cached_photo(message_or_call, photo_url, caption, kb.as_markup())
    else:  # CallbackQuery
        await send_cached_photo(message_or_call.message, photo_url, caption, kb.as_markup())

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