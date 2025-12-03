import os
import asyncio
import logging
import queue
import threading
from flask import Flask, request, jsonify

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.firebase_db import init_firebase
from utils.scheduler import start_scheduler

# Импортируем роутеры
from handlers import start, search, payment, agent, errors
from handlers.property import router as property_router

# --- НАСТРОЙКА ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

# Регистрация роутеров
dp.include_router(start.router)
dp.include_router(search.router)
dp.include_router(payment.router)
dp.include_router(agent.router)
dp.include_router(errors.router)
dp.include_router(property_router)

# --- ОЧЕРЕДЬ И ВОРКЕР ДЛЯ ОБРАБОТКИ ВЕБХУКОВ (ПРАВИЛЬНЫЙ СПОСОБ) ---
update_queue = queue.Queue()

def worker():
    """
    Воркер, который работает в отдельном потоке,
    создает свой собственный asyncio event loop
    и обрабатывает обновления из очереди.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_updates())
    finally:
        loop.close()

async def process_updates():
    """Асинхронная задача для обработки обновлений из очереди."""
    logger.info("Воркер для обработки обновлений запущен.")
    while True:
        try:
            update_json = update_queue.get(block=True) # Блокируем, пока не появится новый элемент
            update = types.Update.model_validate(update_json, context={"bot": bot})
            await dp.feed_update(bot=bot, update=update)
        except Exception as e:
            logger.error(f"Ошибка в воркере при обработке обновления: {e}", exc_info=True)


# --- ВЕБХУК (теперь он быстрый) ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    """
    Этот вебхук больше не ждет обработки. Он просто кладет
    обновление в очередь и немедленно отвечает Telegram.
    """
    try:
        update_queue.put(request.get_json(force=True))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка добавления в очередь вебхука: {e}", exc_info=True)
        return jsonify({"error": "bad request"}), 400

# --- СТАРТАП И ШАТДАУН ---
async def startup():
    init_firebase()
    logger.info("Firebase инициализирован")

    await start_scheduler()
    logger.info("Планировщик OLX запущен")

    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Вебхук установлен: {WEBHOOK_URL}")

    # Запускаем фоновый воркер в отдельном потоке
    threading.Thread(target=worker, daemon=True).start()

async def shutdown():
    logger.info("Остановка бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()

# --- ГАРАНТИРОВАННЫЙ ЗАПУСК ПРИ СТАРТЕ КОНТЕЙНЕРА ---
# Этот блок выполняется один раз при старте Gunicorn/сервера.
try:
    logger.info("Запуск startup-процедуры...")
    asyncio.run(startup())
    logger.info("Startup-процедура завершена.")
except Exception as e:
    logger.critical(f"Критическая ошибка на старте: {e}", exc_info=True)


# --- HEALTH CHECK ---
@app.route("/")
def health():
    return "GoaNest Bot is alive!", 200

# НИКАКОГО if __name__ == "__main__" — Cloud Run использует gunicorn