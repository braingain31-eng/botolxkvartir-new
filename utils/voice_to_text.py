import os
import hashlib
import pickle
import logging
import openai
from openai import OpenAI

logger = logging.getLogger(__name__)

# Инициализация клиента OpenAI (ключ берётся из переменной окружения)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Кэш по file_id — оставляем, это всё ещё даёт огромное ускорение!
CACHE_DIR = "voice_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


async def voice_to_text(file_path: str, file_id: str = None) -> str | None:
    """
    Распознавание голоса через OpenAI Whisper API (whisper-1)
    Супербыстро, суперточно, с кэшированием по file_id
    """
    try:
        # 1. Проверяем кэш по file_id (самое важное ускорение — 0 мс вместо 60–120$)
        if file_id:
            cache_file = os.path.join(CACHE_DIR, f"{hashlib.md5(file_id.encode()).hexdigest()}.pkl")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    text = pickle.load(f)
                logger.info(f"Голос из кэша (OpenAI): {text[:60]}...")
                return text

        # 2. Открываем файл для отправки
        if not os.path.exists(file_path):
            logger.warning(f"Файл не найден: {file_path}")
            return None

        with open(file_path, "rb") as audio_file:
            logger.info(f"Отправляем голосовое в OpenAI Whisper API ({os.path.getsize(file_path)/1024:.1f} KB)")

            # OpenAI сам определяет язык, но можно явно указать
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",                    # Ускоряет + повышает точность для русского
                response_format="text",           # Просто строка, не JSON
                temperature=0.0                   # Максимальная стабильность
            )

        text = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()

        # 3. Кэшируем результат
        if file_id and text:
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(text, f)
                logger.info("Результат закэширован")
            except Exception as e:
                logger.warning(f"Не удалось сохранить кэш: {e}")

        logger.info(f"OpenAI Whisper вернул: {text[:100]}...")
        return text if text else None

    except openai.RateLimitError as e:
        logger.error("OpenAI Rate Limit! Подожди немного...")
        return None
    
    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {e}")
        return None
    
    except Exception as e:
        logger.error(f"Ошибка в voice_to_text (OpenAI): {e}", exc_info=True)
        return None