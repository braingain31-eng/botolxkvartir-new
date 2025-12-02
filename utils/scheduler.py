from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.olx_parser import parse_olx_listing
from database.firebase_db import get_properties
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def run_olx_parser_now():
    """Выполняет парсинг только если прошло более 6 часов с последнего успешного парсинга"""
    try:
        # Получаем последний успешный парсинг
        all_properties = get_properties(limit=1)
        if not all_properties:
            logger.info("База пуста, выполняем парсинг")
        else:
            # Находим самое свежее объявление для определения времени последнего парсинга
            latest_property = max(all_properties, key=lambda x: x.get('parsed_at', ''))
            last_parsed_str = latest_property.get('parsed_at')
            
            if last_parsed_str:
                try:
                    last_parsed_time = datetime.fromisoformat(last_parsed_str.replace('Z', '+00:00'))
                    time_since_last_parse = datetime.now(last_parsed_time.tzinfo) - last_parsed_time
                    
                    if time_since_last_parse < timedelta(hours=6):
                        hours_left = 6 - time_since_last_parse.total_seconds() / 3600
                        logger.info(f"Последний парсинг был {time_since_last_parse.total_seconds()/3600:.1f} часов назад. "
                                  f"Следующий парсинг через {hours_left:.1f} часов.")
                        return
                except Exception as e:
                    logger.warning(f"Не удалось определить время последнего парсинга: {e}. Выполняем парсинг.")
        
        logger.info("Выполняем парсинг OLX...")
        added = await parse_olx_listing()
        logger.info(f"Парсинг завершён. Добавлено: {added} объектов")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении парсинга: {e}")

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


