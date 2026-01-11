# utils/telegram_parser.py — ПАРСЕР TELEGRAM-КАНАЛОВ ДЛЯ АРЕНДЫ В ГОА (Январь 2026)

import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from datetime import datetime
from database.firebase_db import create_property
import config  # API_ID, API_HASH из конфига
import ssl
import re
import time

logger = logging.getLogger(__name__)

# Список каналов
CHANNELS = ['goahouses', 'goaPeople2019', 'goa_appart', 'myflats']

# Ключевые слова для фильтра аренды (расширь по необходимости)
RENT_KEYWORDS = ['аренда', 'rent', 'house', 'villa', 'apartment', 'бунгало', 'flat', 'room', 'сдам', 'сдаю', 'for rent', 'available', 'аренду']

# Список северных районов Гоа для фильтрации
NORTH_GOA_AREAS = [
    "Arambol", "Arambol Beach", "Aswem", "Ashwem", "Mandrem", "Morjim",
    "Kerim", "Keri", "Korgaon", "Siolim", "Chapora", "Vagator", "Anjuna",
    "Assagao", "Arpora", "Baga", "Calangute", "Candolim", "Agarwado", "Pilerne", "Palolem", "Agonda"
]

async def parse_telegram_channels():
    """
    Парсит Telegram-каналы на объявления аренды в северных районах Гоа.
    """
    client = TelegramClient('session', config.API_ID, config.API_HASH)

    async with client:
        try:
            await client.start()
        except SessionPasswordNeededError:
            await client.sign_in(password=input("Введите 2FA-пароль: "))

        total_added = 0
        for channel_username in CHANNELS:
            logger.info(f"Парсим канал: @{channel_username}")

            try:
                channel = await client.get_entity(channel_username)
            except Exception as e:
                logger.error(f"Не удалось получить канал @{channel_username}: {e}")
                continue

            async for msg in client.iter_messages(channel, limit=100):  # Последние 100 сообщений
                if not msg.text:
                    continue

                # Фильтр по ключевым словам аренды
                if not any(word.lower() in msg.text.lower() for word in RENT_KEYWORDS):
                    continue

                # Фильтр по районам (проверяем наличие хотя бы одного района в тексте)
                normalized_text = msg.text.lower().strip()
                area_match = next((area for area in NORTH_GOA_AREAS if area.lower() in normalized_text), None)
                if not area_match:
                    continue

                # Проверяем наличие фото или видео
                photo_url = None
                if msg.photo:
                    photo = msg.photo.sizes[-1]  # Самое большое фото
                    photo_url = await client.download_media(msg.photo, file=f"photos/{msg.id}.jpg")  # Скачиваем локально, можно загрузить в Firebase Storage

                elif msg.video:
                    # Для видео — скачиваем или берём URL
                    photo_url = await client.download_media(msg.video, file=f"videos/{msg.id}.mp4")

                if not photo_url:
                    continue  # Пропускаем без медиа

                # Формируем данные для базы
                ad = {
                    'title': msg.text[:100] + "..." if len(msg.text) > 100 else msg.text,  # Короткий заголовок
                    'description': msg.text,
                    'area': area_match,
                    'price_day_inr': extract_price(msg.text),  # Твоя функция извлечения цены (из OLX, адаптируй)
                    'photos': [photo_url],
                    'source': f"t.me/{channel_username}",
                    'created_at': msg.date.isoformat(),
                    'parsed_at': datetime.utcnow().isoformat(),
                    'id': str(msg.id)  # ID сообщения как уникальный ID
                }

                # Сохраняем в базу
                create_property(ad)
                total_added += 1
                logger.info(f"Добавлено из @{channel_username}: {ad['title']} ({ad['area']})")

            time.sleep(5)  # Пауза между каналами

    logger.info(f"Парсинг завершён. Добавлено {total_added} новых объектов")
    return total_added

# Адаптированная функция извлечения цены из текста (из твоего OLX-кода)
def extract_price(text: str) -> int:
    price_match = re.search(r'₹\s*([\d,]+)', text)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        return int(price_str)
    return 0

# Запуск парсера
if __name__ == '__main__':
    asyncio.run(parse_telegram_channels())