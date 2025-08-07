import uvicorn
import os # <-- Додали імпорт
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router

def create_web_app() -> FastAPI:
    """Створює та конфігурує екземпляр FastAPI."""
    app = FastAPI(
        title="Telegram Bot Web Backend",
        description="API for the bot's Web App admin panel.",
        version="1.0.0"
    )

    app.include_router(router)

    # --- ОНОВЛЕНА ЧАСТИНА ---
    # Будуємо абсолютний шлях до папки webapp
    # Це робить сервер незалежним від того, з якої папки його запустили
    try:
        # __file__ - це шлях до поточного файлу (main.py)
        # os.path.dirname() - отримує папку, де лежить файл
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Піднімаємось на один рівень вище до папки /bot
        bot_dir = os.path.dirname(current_dir)
        # Піднімаємось ще на один рівень до кореня проєкту
        project_root = os.path.dirname(bot_dir)
        # Створюємо шлях до папки webapp
        webapp_path = os.path.join(project_root, "webapp")

        app.mount("/", StaticFiles(directory=webapp_path, html=True), name="webapp")
    except Exception as e:
        print(f"ПОМИЛКА: Не вдалося знайти папку 'webapp'. Переконайтеся, що структура проєкту правильна. {e}")
        print(f"Очікуваний шлях: {webapp_path}")


    return app

async def run_server():
    """Асинхронна функція для запуску веб-сервера."""
    app = create_web_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()