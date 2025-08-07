import asyncio
import logging
from telegram import Update
from bot.core.application import create_application
from bot.core.dispatcher import register_handlers
from bot.infrastructure.database import setup_database
from bot.web_backend.main import run_server
from bot.config import ADMIN_ID


async def main():
    """Головна асинхронна функція запуску всього."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    setup_database()

    app = create_application()
    register_handlers(app)

    logging.info("🚀 Запуск бота та веб-сервера...")
    logging.info(f"📋 Адмін ID: {ADMIN_ID}")

    # Використовуємо більш керований підхід до життєвого циклу.
    # Контекстний менеджер `async with app` автоматично керує
    # app.initialize() на початку та app.shutdown() в кінці.
    try:
        async with app:
            # Запускаємо полінг у фоні
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            # Запускаємо веб-сервер
            # Він буде працювати, доки ми не зупинимо програму
            await run_server()

            # Коректно зупиняємо бота при завершенні run_server (малоймовірно)
            await app.updater.stop()
            await app.stop()
    except Exception as e:
        logging.critical(f"Критична помилка під час роботи програми: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Програму зупинено користувачем.")