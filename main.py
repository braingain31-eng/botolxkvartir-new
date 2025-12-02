import os
import asyncio
import logging
import signal
from datetime import datetime
from flask import Flask, request, jsonify

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database.firebase_db import init_firebase
from handlers import start, search, property, agent, payment, reminders, errors, payment_menu
from utils.olx_parser import parse_olx_listing

# --- Логи ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask + Aiogram ---
app = Flask(__name__)

# Правильный бот для aiogram 3.7+
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

# --- Вебхук ---
WEBHOOK_PATH = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"
WEBHOOK_URL = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

# --- Регистрация хендлеров ---
def register_handlers():
    start.register_handlers(dp)
    search.register_handlers(dp)
    property.register_handlers(dp)
    agent.register_handlers(dp)
    payment.register_handlers(dp)
    payment_menu.register_handlers_payment_menu(dp)
    reminders.register_handlers(dp)
    errors.register_handlers(dp)
    logger.info("Все хендлеры зарегистрированы")

# --- Парсер OLX ---
async def run_olx_parser():
    try:
        logger.info("Запуск планового парсинга OLX...")
        added = await parse_olx_parser()
        logger.info(f"Парсинг завершён. Добавлено: {added}")
    except Exception as e:
        logger.error(f"Ошибка парсинга OLX: {e}", exc_info=True)

# --- Старт ---
@app.before_first_request
def before_first_request():
    asyncio.ensure_future(startup())

async def startup():
    register_handlers()
    init_firebase()
    logger.info("Firebase инициализирован")

    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Вебхук установлен: {WEBHOOK_URL}")

    scheduler.add_job(run_olx_parser, "interval", hours=6, next_run_time=datetime.now())
    scheduler.start()
    logger.info("Планировщик запущен — OLX парсится каждые 6 часов")

# --- Graceful shutdown ---
async def shutdown():
    logger.info("Остановка бота...")
    if scheduler.running:
        scheduler.shutdown()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    logger.info("Бот остановлен")

def handle_sigterm(*_):
    logger.warning("SIGTERM получен — graceful shutdown")
    asyncio.ensure_future(shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)

# --- Вебхук ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") != "application/json":
        return jsonify({"status": "bad request"}), 400

    update = types.Update.model_validate(request.get_json(force=True), context={"bot": bot})
    asyncio.ensure_future(dp.feed_update(bot, update))
    return jsonify({"status": "ok"})

# --- Health check ---
@app.route("/")
def health():
    return "GoaNest Bot живёт и парсит OLX 24/7 на Google Cloud Run!", 200

# --- Запуск ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)