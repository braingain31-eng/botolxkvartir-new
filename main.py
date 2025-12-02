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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

WEBHOOK_PATH = f"/webhook"
WEBHOOK_URL = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

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

async def run_olx_parser():
    try:
        logger.info("Парсинг OLX запущен...")
        added = await parse_olx_listing()
        logger.info(f"Добавлено объявлений: {added}")
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}", exc_info=True)

async def startup():
    register_handlers()
    init_firebase()
    logger.info("Firebase подключён")
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Вебхук установлен: {WEBHOOK_URL}")
    scheduler.add_job(run_olx_parser, "interval", hours=6, next_run_time=datetime.now())
    scheduler.start()
    logger.info("Планировщик запущен")

async def shutdown():
    logger.info("Остановка бота...")
    if scheduler.running:
        scheduler.shutdown()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()

def handle_sigterm(*_):
    asyncio.run(shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)

# ГЛАВНОЕ ИСПРАВЛЕНИЕ — НОВЫЙ EVENT LOOP В КАЖДОМ ПО  ТОКЕ
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update_json = request.get_json(force=True)
        update = types.Update.model_validate(update_json, context={"bot": bot})
        
        # СОЗДАЁМ НОВЫЙ EVENT LOOP ДЛЯ ЭТОГО ПОТОКА
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dp.feed_update(bot, update))
        loop.close()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}", exc_info=True)
        return jsonify({"error": "bad request"}), 400

@app.route("/")
def health():
    return "GoaNest Bot ЖИВЁТ НАВСЕГДА — Cloud Run — Декабрь 2025", 200

# Запуск стартапа
if __name__ == "__main__":
    asyncio.run(startup())
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)