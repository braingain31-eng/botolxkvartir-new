from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.firebase_db import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

REMINDERS = [
    "Вы смотрели виллу, но не связались. Прямая бронь — дешевле!",
    "80% жилья — у частников. Только у нас — прямые контакты.",
    "Обновлено 47 новых объектов! Хотите контакты?",
    "«Нашёл бунгало за 40к ₿» — отзыв Алексея",
    "Мы — №1 по охвату в Гоа. Всё в одной базе.",
    "Цены растут! Забронируй по старой цене.",
    "Приведи друга — +3 дня бесплатно!",
    "Последний шанс: оплатите за 10$"
]

async def send_reminders(bot: Bot):
    """
    Отправляет напоминания пользователям, которые просматривали объекты,
    не имеют активной подписки и не заходили больше суток.
    """
    try:
        users_ref = db.collection('users')
        docs = users_ref.stream()

        for doc in docs:
            user = doc.to_dict()
            user_id = int(doc.id)

            is_unpaid = user.get('paid_until') is None
            has_viewed = user.get('viewed_properties')

            if is_unpaid and has_viewed:
                last_seen_str = user.get('last_seen')
                if last_seen_str:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen_str)
                        # Убираем информацию о часовом поясе для сравнения
                        if last_seen_dt.tzinfo:
                            last_seen_dt = last_seen_dt.replace(tzinfo=None)

                        if last_seen_dt < datetime.utcnow() - timedelta(days=1):
                            reminder_idx = len(user['viewed_properties']) % len(REMINDERS)
                            await bot.send_message(
                                user_id,
                                REMINDERS[reminder_idx],
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    # В старом коде было pay_7, в тексте 10$. Оставляю pay_10_usd как более логичное
                                    [InlineKeyboardButton("Оплатить 10$", callback_data="pay_10_usd")]
                                ])
                            )
                    except Exception as e:
                        logger.error(f"Не удалось отправить напоминание пользователю {user_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей для напоминаний: {e}")


def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(send_reminders, "cron", hour=10, args=[bot])
    scheduler.start()
    logger.info("Планировщик напоминаний запущен.")

# Force update
