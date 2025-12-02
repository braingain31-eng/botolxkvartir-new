import os
from faster_whisper import WhisperModel  # Локальный STT (бесплатно)
from openai import AsyncOpenAI
import logging
import config

# Инициализация локального Whisper (скачает модель ~1GB при первом запуске)
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")  # "small" для точности, "base" для скорости

# OpenRouter прокси для Grok-4 (бесплатно, OpenAI-совместимый)
# Зарегистрируйся на openrouter.ai (бесплатно), получи API-ключ
grok_client = AsyncOpenAI(
    api_key=config.OPENROUTER_API_KEY,  # Твой ключ от OpenRouter
    base_url="https://openrouter.ai/api/v1",  # Прокси-эндпоинт
)

async def voice_to_text(file_path: str) -> str | None:
    """
    1. Локальный STT (Whisper) → текст из аудио.
    2. Grok-4 уточняет/улучшает текст (для поиска жилья в Гоа).
    """
    try:
        # Шаг 1: Транскрипция аудио (локально, бесплатно)
        segments, _ = whisper_model.transcribe(file_path, language="ru")  # Поддержка RU/EN
        raw_text = " ".join(segment.text.strip() for segment in segments).strip()
        
        if not raw_text:
            logging.warning("Whisper не распознал аудио")
            return None
        
        # Шаг 2: Уточнение через Grok-4 (бесплатный прокси)
        prompt = f"""
        Ты ассистент по поиску жилья в Гоа. Пользователь сказал: "{raw_text}".
        
        Уточни и структурируй запрос для поиска:
        - Тип жилья (вилла, бунгало, комната)?
        - Бюджет (в $/сутки или рупиях)?
        - Даты (заезд/выезд)?
        - Район (Анжуна, Арпора, Вагатор)?
        - Кол-во человек?
        - Другие пожелания (бассейн, Wi-Fi)?
        
        Верни только структурированный текст на русском, без лишнего.
        """
        
        response = await grok_client.chat.completions.create(
            model="x-ai/grok-4.1-fast:free",  # Бесплатная Grok-4.1 Fast на OpenRouter
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1,  # Низкая креативность для точности
        )
        
        refined_text = response.choices[0].message.content.strip()
        logging.info(f"Raw: '{raw_text}' → Refined by Grok: '{refined_text}'")
        return refined_text
        
    except Exception as e:
        logging.error(f"Voice-to-text error: {e}")
        return None  # Fallback: верни raw_text, если Grok упал