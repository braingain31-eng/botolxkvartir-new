import os
import asyncio
import logging
from flask import Flask, request, jsonify

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database.firebase_db import init_firebase
from utils.scheduler import start_scheduler  # ← ТВОЙ ПЛАНИРОВЩИК

# Импортируем роутеры
from handlers import start, search, payment, agent, errors
from handlers.property import router as property_router

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

# --- ПАРСЕР OLX ---
async def run_olx_parser():
    try:
        logger.info("Запуск планового парсинга OLX...")
        added = await parse_olx_listing()
        logger.info(f"Парсинг завершён. Добавлено: {added} новых объявлений")
    except Exception as e:
        logger.error(f"Ошибка парсинга OLX: {e}", exc_info=True)

# --- СТАРТАП ---
async def startup():
    init_firebase()
    logger.info("Firebase инициализирован")

    await start_scheduler()  # ← ВОТ ОНО! ПЛАНИРОВЩИК ЗАПУЩЕН!
    logger.info("Планировщик OLX запущен — парсит каждые 6 часов")

    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Вебхук установлен: {WEBHOOK_URL}")

# --- ШАТДАУН ---
async def shutdown():
    logger.info("Остановка бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()

# --- ГАРАНТИРОВАННЫЙ ЗАПУСК ПРИ СТАРТЕ КОНТЕЙНЕРА ---
asyncio.get_event_loop().run_until_complete(startup())

# --- ВЕБХУК ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        update = types.Update.model_validate(request.get_json(force=True), context={"bot": bot})
        
        future = dp.feed_update(bot=bot, update=update)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(future)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Ошибка вебхука: {e}", exc_info=True)
        return jsonify({"error": "bad request"}), 400

# --- HEALTH ---
@app.route("/")
def health():
    return "GoaNest Bot ЖИВЁТ НАВСЕГДА — парсит OLX каждые 6 часов — декабрь 2025", 200

# НИКАКОГО if __name__ == "__main__" — Cloud Run использует gunicorn