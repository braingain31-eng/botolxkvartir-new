import os
import hashlib
import pickle
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Глобальная модель — грузится один раз при старте контейнера
# tiny — 39M параметров, 5–10× быстрее base, качество всё ещё отличное для русского
whisper_model = WhisperModel(
    "tiny",                    # ← САМОЕ БЫСТРОЕ И ДОСТАТОЧНО ТОЧНОЕ
    device="cpu",
    compute_type="int8",       # Максимальная оптимизация на CPU
    download_root="/tmp/whisper_models"  # Кешируем в /tmp (Cloud Run сохраняет между cold start'ами)
)

# Кэш по file_id (чтобы одно и то же голосовое не распознавать 100 раз)
CACHE_DIR = "voice_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

async def voice_to_text(file_path: str, file_id: str = None) -> str | None:
    """
    Супербыстрое распознавание голоса (0.3–1.5 сек на 5-сек голосовуху)
    """
    try:
        # 1. Кэш по file_id (самое важное ускорение)
        if file_id:
            cache_file = os.path.join(CACHE_DIR, f"{hashlib.md5(file_id.encode()).hexdigest()}.pkl")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    text = pickle.load(f)
                logger.info(f"Голос из кэша: {text[:50]}...")
                return text

        # 2. Самое быстрое распознавание
        logger.info("Запуск faster-whisper tiny (очень быстро)")
        segments, info = whisper_model.transcribe(
            file_path,
            beam_size=1,           # 1 = максимальная скорость (для tiny хватает)
            best_of=1,             # ещё быстрее
            patience=1.0,
            language="ru",
            temperature=0.0,       # детерминированно
            word_timestamps=False
        )

        text = " ".join(seg.text for seg in segments).strip()

        # 3. Сохраняем в кэш
        if file_id and text:
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(text, f)
            except:
                pass  # не критично

        logger.info(f"Голос распознан за {info.duration:.1f}с: {text[:100]}...")
        return text if text else None

    except Exception as e:
        logger.error(f"Ошибка voice_to_text: {e}", exc_info=True)
        return None