# utils/telegram_parser.py — ПАРСЕР TELEGRAM-КАНАЛОВ ДЛЯ АРЕНДЫ В ГОА (Январь 2026)

import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from datetime import datetime
from database.firebase_db import create_property
import config  # API_ID, API_HASH из конфига
import re
import time
import os

logger = logging.getLogger(__name__)

# Создаём папку для медиа
os.makedirs("media/photos", exist_ok=True)
os.makedirs("media/videos", exist_ok=True)

# Список каналов (username без @)
CHANNELS = ['goahouses', 'goaPeople2019', 'goa_appart', 'myflats']

# Ключевые слова для фильтра аренды
RENT_KEYWORDS = [
    'аренда', 'rent', 'house', 'villa', 'apartment', 'бунгало', 'flat', 'room',
    'сдам', 'сдаю', 'for rent', 'available', 'аренду', 'long term', 'short term'
]

# Районы для фильтрации
NORTH_GOA_AREAS = [
    "Arambol", "Arambol Beach", "Aswem", "Ashwem", "Mandrem", "Morjim",
    "Kerim", "Keri", "Korgaon", "Siolim", "Chapora", "Vagator", "Anjuna",
    "Assagao", "Arpora", "Baga", "Calangute", "Candolim", "Agarwado", "Pilerne"
]

async def parse_telegram_channels():
    """
    Парсит указанные каналы, ищет объявления аренды в северных районах Гоа.
    Сохраняет в Firestore через create_property.
    """
    client = TelegramClient('session', api_id=None, api_hash=None)

    async with client:
        try:
            await client.start(bot_token=config.TELEGRAM_BOT_TOKEN)
            logger.info("Telethon клиент успешно авторизован")
        except SessionPasswordNeededError:
            logger.warning("Требуется 2FA-пароль")
            password = input("Введите 2FA-пароль: ")
            await client.sign_in(password=password)

        total_added = 0

        for channel_username in CHANNELS:
            logger.info(f"Парсим канал: @{channel_username}")

            try:
                channel = await client.get_entity(channel_username)
            except Exception as e:
                logger.error(f"Не удалось получить канал @{channel_username}: {e}")
                continue

            async for msg in client.iter_messages(channel, limit=100):
                if not msg.text:
                    continue

                text_lower = msg.text.lower()

                # Фильтр по ключевым словам аренды
                if not any(word in text_lower for word in RENT_KEYWORDS):
                    continue

                # Фильтр по районам
                area_match = next((area for area in NORTH_GOA_AREAS if area.lower() in text_lower), None)
                if not area_match:
                    continue

                # Проверяем наличие медиа
                media_url = None
                media_type = None

                if msg.photo:
                    media_url = await client.download_media(msg.photo, file=f"media/photos/{msg.id}.jpg")
                    media_type = "photo"
                elif msg.video:
                    media_url = await client.download_media(msg.video, file=f"media/videos/{msg.id}.mp4")
                    media_type = "video"

                if not media_url:
                    continue  # Пропускаем без медиа

                # Извлекаем цену (адаптировано из твоего OLX-парсера)
                price = extract_price(msg.text)

                # Формируем объект для базы
                ad = {
                    'title': (msg.text[:100] + "...") if len(msg.text) > 100 else msg.text,
                    'description': msg.text,
                    'area': area_match,
                    'price_day_inr': price,
                    'photos': [str(media_url)] if media_url else [],
                    'source': f"t.me/{channel_username}",
                    'source_type': 'telegram',
                    'message_id': msg.id,
                    'created_at': msg.date.isoformat(),
                    'parsed_at': datetime.utcnow().isoformat()
                }

                # Сохраняем в базу
                create_property(ad)
                total_added += 1
                logger.info(f"Добавлено из @{channel_username}: {ad['title']} ({ad['area']}) — {price} ₹")

            time.sleep(5)  # Пауза между каналами

        logger.info(f"Парсинг завершён. Добавлено {total_added} новых объектов")
        return total_added

def extract_price(text: str) -> int:
    """Извлекает цену в рупиях из текста"""
    price_match = re.search(r'(?:₹|Rs\.?|Rupees?)\s*([\d,]+)', text, re.IGNORECASE)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        return int(price_str)
    
    # Альтернатива: просто цифры рядом с "per day" или "daily"
    price_match = re.search(r'(\d{3,6})\s*(?:per day|daily|night|сутки|день)', text, re.IGNORECASE)
    if price_match:
        return int(price_match.group(1))
    
    return 0  # Нет цены — 0

# Запуск парсера (для теста локально)
if __name__ == '__main__':
    asyncio.run(parse_telegram_channels())