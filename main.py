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

# --- ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ---
# Эти объекты создаются в основном потоке, но будут использоваться
# в фоновом потоке, где запущен asyncio loop.
update_queue = queue.Queue()
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
app = Flask(__name__)

# Регистрация роутеров
dp.include_router(start.router)
dp.include_router(search.router)
dp.include_router(payment.router)
dp.include_router(agent.router)
dp.include_router(errors.router)
dp.include_router(property_router)

# --- URL Вебхука ---
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{config.WEBHOOK_BASE_URL}{WEBHOOK_PATH}"


# --- АСИНХРОННЫЙ ВОРКЕР (СЕРДЦЕ БОТА) ---

async def process_updates():
    logger.info("[WEBHOOK DIAG 4/4] Воркер для обработки обновлений запущен и ждёт из очереди...")
    while True:
        try:
            update_json = update_queue.get(block=True)
            update_id = update_json.get("update_id", "NO_ID")
            logger.info(f"[WEBHOOK DIAG SUCCESS] Достаём из очереди update_id={update_id} и начинаем обработку")  # ← ДОБАВЬ ЭТУ СТРОЧКУ
            
            update = types.Update.model_validate(update_json, context={"bot": bot})
            await dp.feed_update(bot=bot, update=update)
            logger.info(f"[WEBHOOK DIAG DONE] update_id={update_id} успешно обработан")
        except Exception as e:
            logger.error(f"[WEBHOOK DIAG FAIL] Ошибка при обработке update_id={update_id}: {e}", exc_info=True)

async def main_async_logic():
    """Выполняет асинхронный старт и запускает обработку обновлений."""
    init_firebase()
    logger.info("Firebase инициализирован")

    start_scheduler()
    logger.info("Планировщик OLX запущен")

    logger.info("Устанавливаем вебхук...")
    try:
        result = await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True,
            timeout=10  # ← явно указываем короткий таймаут
        )
        logger.info(f"Вебхук успешно установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"НЕ УДАЛОСЬ установить вебхук: {e}")
        logger.error(f"URL был: {WEBHOOK_URL}")
        # НЕ прерываем выполнение — продолжаем работу бота даже без вебхука
        logger.warning("Продолжаем работу без вебхука (можно переключиться на polling позже")

    logger.info("[WEBHOOK DIAG 4/4] Воркер обработки обновлений СТАРТАНУЛ — начинаем читать очередь")
    await process_updates()  # ← теперь точно дойдёт сюда

def worker():
    """
    Создает и управляет event loop'ом в отдельном потоке.
    Это центральное место для всей asyncio-логики.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main_async_logic())
    except asyncio.CancelledError:
        logger.info("Воркер был остановлен.")
    finally:
        logger.info("Закрытие сессии бота и event loop'а...")
        loop.run_until_complete(bot.session.close())
        loop.close()

# --- ВЕБ-СЕРВЕР (FLASK) ---

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    """Мгновенно принимает обновления от Telegram и кладет в очередь."""
    logger.info("[WEBHOOK DIAG 1/4] → Telegram прислал POST на /webhook")   # ← ДОБАВЬ ЭТУ СТРОЧКУ
    try:
        update_json = request.get_json(force=True)
        update_id = update_json.get("update_id", "NO_ID")
        logger.info(f"[WEBHOOK DIAG 2/4] Получен update_id={update_id}, кладём в очередь")  # ← И ЭТУ
        
        update_queue.put(update_json)
        logger.info(f"[WEBHOOK DIAG 3/4] update_id={update_id} успешно добавлен в очередь (размер очереди сейчас: {update_queue.qsize()})")  # ← И ЭТУ
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"[WEBHOOK DIAG ERROR] Ошибка добавления в очередь: {e}", exc_info=True)
        return jsonify({"error": "bad request"}), 400

@app.route("/")
def health_check():
    """Проверка жизнеспособности для Cloud Run."""
    return "GoaNest Bot is alive!", 200

# --- ЗАПУСК ---
# Gunicorn (или другой WSGI-сервер) загрузит этот файл.
# Мы запускаем наш асинхронный воркер в фоновом потоке.
# daemon=True гарантирует, что поток закроется вместе с основным процессом.
logger.info("Запуск фонового потока для asyncio воркера...")
threading.Thread(target=worker, daemon=True).start()
