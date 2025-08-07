from telegram.ext import Application
from bot.config import BOT_TOKEN

def create_application() -> Application:
    """Створює та повертає екземпляр Application."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не знайдено! Перевірте .env файл.")
    return Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()