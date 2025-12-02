import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database.firebase_db import init_firebase
from utils.scheduler import start_scheduler

# Импортируем роутеры (убедись, что они у тебя на aiogram 3.x с роутерами)
from handlers import start, search, payment, agent, errors, payment_menu
from handlers.property import router as property_router
# если reminders и другие — тоже подключи

# --- Логи ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Бот и диспетчер ---
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# --- Планировщик ---
scheduler = AsyncIOScheduler()

async def main():
    # Инициализация Firebase
    init_firebase()
    .info("Firebase инициализирован")

    # Запуск твоего кастомного планировщика (если есть)
    await start_scheduler()

    # Регистрация всех роутеров
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(payment.router)
    dp.include_router(agent.router)
    dp.include_router(errors.router)
    dp.include_router(payment_menu.router)
    dp.include_router(property_router)
    # добавь остальные, если есть

    .info("Все роутеры подключены")

    # УДАЛЯЕМ ВЕБХУК ПРИ СТАРТЕ (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)
    .info("Старый вебхук удалён")

    .info("Бот запущен в режиме polling — работает 24/7 на Render!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        .info("Бот остановлен")