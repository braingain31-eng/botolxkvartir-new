from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.olx_parser import parse_olx_listing
from utils.telegram_parser import parse_telegram_channels
from database.firebase_db import get_properties
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def run_olx_parser_now():
    """Парсит OLX только если прошло ≥6 часов с последнего УСПЕШНОГО парсинга"""
    try:
        # Берём ВСЁ, но только поле parsed_at (экономим трафик)
        props = get_properties(order_by="-parsed_at", limit=1)  # ← САМОЕ ГЛАВНОЕ ИЗМЕНЕНИЕ
        
        if not props:
            logger.info("База пуста → запускаем парсинг")
        else:
            latest = props[0]  # уже отсортировано по убыванию → первое = самое новое
            parsed_at_str = latest.get("parsed_at")
            
            if not parsed_at_str:
                logger.info("В базе есть объекты, но нет поля parsed_at → запускаем парсинг")
            else:
                try:
                    # Правильно парсим ISO с Z
                    parsed_at = datetime.fromisoformat(parsed_at_str.replace("Z", "+00:00"))
                    now = datetime.now(parsed_at.tzinfo)
                    hours_since = (now - parsed_at).total_seconds() / 3600

                    if hours_since < 6:
                        logger.info(f"Последний парсинг был {hours_since:.1f} ч назад → пропускаем (ещё рано)")
                        return
                    else:
                        logger.info(f"Последний парсинг был {hours_since:.1f} ч назад → пора обновлять")
                except Exception as e:
                    logger.warning(f"Ошибка парсинга даты parsed_at: {e} → запускаем парсинг на всякий случай")

        # NEW: Парсинг Telegram-каналов
        logger.info("Начинаем парсинг Telegram-каналов...")
        tg_added = await parse_telegram_channels()
        logger.info(f"Telegram-парсинг завершён. Добавлено новых: {tg_added}")

        # # Если дошли сюда — парсим
        # logger.info("Начинаем парсинг OLX...")
        # added = await parse_olx_listing()
        # logger.info(f"Парсинг завершён. Добавлено новых: {added}")

    except Exception as e:
        logger.error(f"Критическая ошибка в run_olx_parser_now: {e}", exc_info=True)

async def start_scheduler():
    """Запускает планировщик с проверкой времени последнего парсинга"""
    # НЕ выполняем немедленный парсинг при старте
    # Вместо этого сразу ставим задачу на регулярное выполнение

    # При запуске сразу проверяем и выполняем парсинг при необходимости
    logger.info("Запуск планировщика. Проверка необходимости парсинга...")
    await run_olx_parser_now()
    
    # Удаляем все существующие задачи парсинга
    if scheduler.get_job("olx_every_6h"):
        scheduler.remove_job("olx_every_6h")
    
    # Добавляем регулярную задачу каждые 6 часов
    scheduler.add_job(
        run_olx_parser_now,
        trigger="interval",
        hours=6,
        id="olx_every_6h",
        replace_existing=True,
        next_run_time=datetime.now()  # первый запуск через 6 часов после добавления
    )
    
    scheduler.start()
    logger.info("Планировщик OLX запущен: парсинг каждые 6 часов")


