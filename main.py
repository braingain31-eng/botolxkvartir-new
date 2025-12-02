import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
from database.firebase_db import init_firebase
from utils.scheduler import start_scheduler

# Подключаем роутеры
from handlers import start, search, payment, agent, errors, payment_menu
from handlers.property import router as property_router

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Бот с правильным DefaultBotProperties (aiogram 3.7+)
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def main():
    logger.info("Запуск бота в режиме polling...")

    # Firebase
    init_firebase()
    logger.info("Firebase подключён")

    # Твой планировщик
    await start_scheduler()
    logger.info("Планировщик запущен")

    # Роутеры
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(payment.router)
    dp.include_router(agent.router)
    dp.include_router(errors.router)
    dp.include_router(payment_menu.router)
    dp.include_router(property_router)

    logger.info("Все роутеры подключены")

    # Удаляем старый вебхук (чтобы не мешал)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Старый вебхук удалён")

    logger.info("Бот запущен в polling-режиме — работает 24/7 на Render!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")