import os
import logging
from dotenv import load_dotenv

# Завантажуємо змінні оточення з .env файлу
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://1744a1778de4.ngrok-free.app/") # URL для Web App

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    logging.critical("ПОМИЛКА: Перевірте, що ADMIN_ID вказано у файлі .env і є числом.")
    exit()

DB_NAME = "bot_database_v6.db"