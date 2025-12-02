# main_bot.py
import asyncio
import logging
import signal
from datetime import datetime

from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from handlers import start, search, property, agent, payment, reminders, errors, payment_menu
from utils.olx_parser import parse_olx_listing

# --- Логи -- -
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask + Aiogram ---
app = Flask(__name__)
bot = Bot(token=config.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

# --- Вебхук ---
WEBHOOK_PATH = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"
WEBHOOK_URL = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

# --- Регистрация всех хендлеров ---
def register_handlers():
    start.register_handlers(dp)
    search.register_handlers(dp)
    property.register_handlers(dp)
    agent.register_handlers(dp)
    payment.register_handlers(dp)
    payment_menu.register_handlers_payment_menu(dp)
    reminders.register_handlers(dp)
    errors.register_handlers(dp)
    logger.info("Все обработчики зарегистрированы")

# --- Фоновая задача: парсинг OLX ---
async def run_olx_parser():
    try:
        logger.info("Запуск планового парсинга OLX...")
        added = await parse_olx_listing()
        logger.info(f"Парсинг завершён. Добавлено новых объявлений: {added}")
    except Exception as e:
        logger.error(f"Ошибка в фоновом парсинге OLX: {e}", exc_info=True)

# --- Запуск при старте контейнера ---
@app.before_serving
async def startup():
    register_handlers()

    # Установка вебхука
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Вебхук установлен: {WEBHOOK_URL}")

    # Запуск планировщика
    scheduler.add_job(run_olx_parser, "interval", hours=6, next_run_time=datetime.now())
    scheduler.start()
    logger.info("Планировщик запущен — парсинг OLX каждые 6 часов")

# --- Остановка ---
async def shutdown():
    logger.info("Остановка бота...")
    if scheduler.running:
        scheduler.shutdown()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    logger.info("Бот остановлен")

def handle_sigterm(*_):
    logger.warning("Получен SIGTERM — graceful shutdown")
    asyncio.create_task(shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)

# --- Вебхук-роут ---
@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = types.Update.model_validate(request.get_json(force=True), context={"bot": bot})
    await dp.feed_update(bot, update)
    return jsonify({"status": "ok"})

# --- Health check ---
@app.route("/")
def health():
    return "GoaNest Bot жив и работает!", 200

# --- Для локального запуска (не используется в Cloud Run) ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)