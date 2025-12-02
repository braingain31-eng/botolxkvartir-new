# utils/voice_handler.py  ← создай этот файл

import os
import aiofiles
from aiogram import types
from utils.voice_to_text import voice_to_text 
# Создаём папку один раз при старте бота
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

async def download_voice(message: types.Message) -> str | None:
    """
    Безопасно скачивает голосовое сообщение и возвращает путь к файлу
    """
    voice: types.Voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    
    # Генерируем уникальное имя файла
    file_path = os.path.join(TEMP_DIR, f"{voice.file_unique_id}.ogg")
    
    # Скачиваем напрямую в нужную папку
    await message.bot.download_file(file.file_path, file_path)
    
    return file_path


async def voice_to_text_safe(file_path: str) -> str:
    """
    Твой существующий voice_to_text, но с удалением файла после использования
    """
    try:
        text = await voice_to_text(file_path)
        return text.strip() if text else ""
    finally:
        # Удаляем файл, чтобы не засорять диск
        try:
            os.remove(file_path)
        except:
            pass