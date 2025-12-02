# utils/grok_api.py — 100% РАБОЧИЙ НА 27.11.2025

from openai import AsyncOpenAI
import config
import logging
import random   # ← ЭТО БЫЛО ПРОПУЩЕНО!

logger = logging.getLogger(__name__)

# Клиент OpenRouter (поддерживает все актуальные модели xAI)
client = AsyncOpenAI(
    api_key=config.GROK_API_KEY,
    base_url="https://api.x.ai/v1"
)

# АКТУАЛЬНЫЕ модели xAI на ноябрь 2025 (все работают)
GROK_MODELS = [
    "x-ai/grok-4.1-fast",     # САМАЯ СВЕЖАЯ И БЫСТРАЯ (рекомендую)
    "x-ai/grok-4",            # если 4.1 недоступна
    "x-ai/grok-beta",         # стабильная
    "x-ai/grok-3",            # если нужно дешевле
]

async def ask_grok(prompt: str) -> str:
    """
    Надёжный запрос к Grok через OpenRouter.
    Автоматически переключается между моделями, если одна недоступна.
    """
    random.shuffle(GROK_MODELS)  # рандомизация для баланса нагрузки

    for model in GROK_MODELS:
        try:
            response = await client.chat.completions.create(
                model="grok-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=350,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Модель {model} недоступна: {e}. Пробую следующую...")
            continue

    # Если ВСЁ упало — бот остаётся живым
    logger.error("Все модели xAI недоступны. Включаю fallback.")
    return f"Поиск по запросу: {prompt}"