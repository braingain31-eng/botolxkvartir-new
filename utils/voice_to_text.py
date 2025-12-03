import os
from faster_whisper import WhisperModel  # Локальный STT (бесплатно)
from openai import AsyncOpenAI
import logging
import config
import hashlib
import pickle

# Инициализация локального Whisper (скачает модель ~1GB при первом запуске)
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")  # "small" для точности, "base" для скорости

# OpenRouter прокси для Grok-4 (бесплатно, OpenAI-совместимый)
# Зарегистрируйся на openrouter.ai (бесплатно), получи API-ключ
grok_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,  # Твой ключ от OpenRouter
    base_url="https://openrouter.ai/api/v1",  # Прокси-эндпоинт
)

async def voice_to_text(file_path: str, file_id: str = None) -> str | None:
    """
    1. Локальный STT (Whisper) → текст из аудио.
    2. Grok-4 уточняет/улучшает текст (для поиска жилья в Гоа).
    """
    try:
        if file_id:
                cache_dir = "voice_cache"
                os.makedirs(cache_dir, exist_ok=True)
                cache_file = f"{cache_dir}/{hashlib.md5(file_id.encode()).hexdigest()}.pkl"
                if os.path.exists(cache_file):
                    with open(cache_file, "rb") as f:
                        return pickle.load(f)

        # Распознавание
        segments, _ = model.transcribe(file_path, beam_size=5, language="ru")
        text = " ".join(segment.text for segment in segments).strip()

        # Сохраняем в кэш
        if file_id and text:
            with open(cache_file, "wb") as f:
                pickle.dump(text, f)

        return text
        
    except Exception as e:
        logging.error(f"Voice-to-text error: {e}")
        return None  # Fallback: верни raw_text, если Grok упал