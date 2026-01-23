# utils/telegram_parser.py — ПАРСЕР TELEGRAM-КАНАЛОВ ДЛЯ АРЕНДЫ В ГОА (Январь 2026)

import logging
import asyncio
import os
import uuid
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from datetime import datetime
from database.firebase_db import create_property
from utils.firestore_session import FirestoreSession
from firebase_admin import storage
import config  # TELEGRAM_BOT_TOKEN, другие настройки
import re
import time


logger = logging.getLogger(__name__)

# Создаём папки для медиа (если не существуют)
TEMP_MEDIA_DIR = "temp_media"
os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)

# Список каналов (username без @)
CHANNELS = ['goahouses', 'goaPeople2019', 'goa_appart', 'myflats']

# Ключевые слова для фильтра аренды (расширь при необходимости)
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
    # Уникальный ID воркера для сессии
    # worker_id = os.getenv('GUNICORN_WORKER_ID', str(uuid.uuid4())[:8])
    # session_name = f'session_telegram_parser_{worker_id}'
    logger.info(f"Старт -----  ")
    session_name = FirestoreSession(session_name='telegram_parser')

    # # === ЛОГИ СЕССИИ ===
    # session_path = f"{session_name}.session"
    # logger.info(f"Попытка загрузки сессии: {session_path}")
    # if os.path.exists(session_path):
    #     logger.info(f"Файл сессии найден: {os.path.getsize(session_path)} байт")
    # else:
    #     logger.warning(f"Файл сессии НЕ НАЙДЕН: {session_path} — будет создана новая сессия")
    # === КОНЕЦ ЛОГОВ СЕССИИ ===

    client = TelegramClient(session_name, config.API_ID, config.API_HASH)

    async with client:
        try:
            # Авторизация через Bot Token
            await client.start(bot_token=config.TELEGRAM_BOT_TOKEN)
            logger.info(f"Telethon успешно авторизован через Bot Token ")
            logger.info(f"Сессия сохранена/загружена")
        except SessionPasswordNeededError:
            logger.error("Требуется 2FA-пароль — запусти локально для ввода")
            raise
        except Exception as e:
            logger.error(f"Критическая ошибка авторизации: {e}")
            raise

        total_added = 0

        for channel_username in CHANNELS:
            logger.info(f"Парсим канал: @{channel_username}")

            try:
                # Получаем entity канала
                channel = await client.get_entity(channel_username)
            except Exception as e:
                logger.error(f"Не удалось получить канал @{channel_username}: {e}")
                continue

            # Берём последние 100 сообщений (можно увеличить до 200–500)
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

                # Проверяем наличие медиа (фото или видео)
                media_url = None
                media_type = None

                if msg.photo or msg.video:
                    file_path = await client.download_media(msg, file=f"{TEMP_MEDIA_DIR}/{msg.id}")
                    if file_path:
                        # Загружаем в Storage
                        media_url = await upload_to_storage(file_path, msg.id)
                        # Удаляем временный файл
                        os.remove(file_path)    

                if not media_url:
                    continue  # Пропускаем без медиа

                # Извлечение цены (адаптировано из OLX-парсера)
                price = extract_price(msg.text)

                # Формируем объект для базы
                ad = {
                    'title': (msg.text[:100] + "...") if len(msg.text) > 100 else msg.text,
                    'description': msg.text,
                    'area': area_match,
                    'price_day_inr': price,
                    'photos': [media_url] if media_url else [],
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


async def upload_to_storage(file_path: str, msg_id: int) -> str:
    """
    Загружает файл в Firebase Storage и возвращает публичную ссылку.
    """
    bucket = storage.bucket(config.FIREBASE_BUCKET)  # В config добавь FIREBASE_BUCKET = 'botolxkvartir.appspot.com'
    filename = os.path.basename(file_path)
    blob = bucket.blob(f"media/{msg_id}/{filename}")

    # Загружаем файл
    blob.upload_from_filename(file_path)

    # Делаем публичным (если нужно, иначе используй signed URL)
    blob.make_public()

    logger.info(f"Медиа загружено: {blob.public_url}")
    return blob.public_url


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