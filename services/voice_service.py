import os
import aiohttp
import aiofiles
import tempfile
from openai import AsyncOpenAI

whisper_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def transcribe_voice(file_path: str) -> str:
    """Транскрибируем голосовое сообщение через Whisper"""
    async with aiofiles.open(file_path, "rb") as f:
        audio_data = await f.read()

    # Whisper принимает файл — открываем как обычный файл
    with open(file_path, "rb") as audio_file:
        response = await whisper_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru"  # Указываем русский для точности
        )

    return response.text


async def download_voice(bot, file_id: str) -> str:
    """Скачиваем голосовое сообщение от Telegram"""
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Создаём временный файл
    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp_path = tmp.name
    tmp.close()

    # Скачиваем файл
    await bot.download_file(file_path, tmp_path)
    return tmp_path


async def cleanup_file(file_path: str):
    """Удаляем временный файл"""
    try:
        os.unlink(file_path)
    except Exception:
        pass
