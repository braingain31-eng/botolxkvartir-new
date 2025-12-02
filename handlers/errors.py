# handlers/errors.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ErrorEvent
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
import logging

router = Router()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Универсальный обработчик ошибок
@router.errors()
async def error_handler(event: ErrorEvent):
    exception = event.exception
    user_id = event.update.message.from_user.id if event.update.message else "unknown"
    
    logger.error(f"Ошибка у пользователя {user_id}: {exception}", exc_info=True)
    
    try:
        await event.update.message.answer(
            "Произошла ошибка. Попробуйте позже.\n"
            "Если проблема повторяется — напишите @support_goa"
        )
    except:
        pass  # Если не удалось отправить

# Специфичные ошибки
@router.message(F.text.contains("ошибка"))
async def catch_user_error(message: Message):
    await message.answer("Мы уже работаем над этим! Попробуйте позже.")