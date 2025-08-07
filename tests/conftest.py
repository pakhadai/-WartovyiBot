import pytest
import sqlite3
from unittest.mock import patch


# --- Клас-обгортка для безпечного тестування з'єднання ---
class MockConnection:
    """
    Цей клас-обгортка імітує sqlite3.Connection, але має "безпечний" метод close(),
    який нічого не робить. Всі інші запити (наприклад, .cursor()) він передає
    справжньому об'єкту з'єднання.
    """

    def __init__(self, real_connection):
        self._real_connection = real_connection

    def close(self):
        # Цей метод навмисно порожній, щоб запобігти закриттю справжнього з'єднання.
        pass

    def __getattr__(self, name):
        # Якщо викликається будь-який інший метод (наприклад, .cursor(), .commit()),
        # передаємо цей виклик справжньому об'єкту з'єднання.
        return getattr(self._real_connection, name)


# --- Фікстура для бази даних (ФІНАЛЬНА ВЕРСІЯ) ---
@pytest.fixture(scope="function")
def test_db(monkeypatch):
    """
    Створює тимчасову базу даних і використовує клас-обгортку,
    щоб запобігти її закриттю всередині функцій, що тестуються.
    """
    # 1. Створюємо справжнє з'єднання в пам'яті
    real_conn = sqlite3.connect(":memory:")

    # 2. Створюємо екземпляр нашої безпечної обгортки
    mock_conn_wrapper = MockConnection(real_conn)

    # 3. Підміняємо sqlite3.connect так, щоб він завжди повертав нашу обгортку
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: mock_conn_wrapper)

    # 4. Налаштовуємо схему бази даних.
    #    Тепер setup_database отримає нашу обгортку і буде працювати з нею.
    from bot.infrastructure.database import setup_database
    setup_database()

    # 5. Передаємо керування тесту
    yield real_conn

    # 6. Після завершення тесту закриваємо справжнє з'єднання
    real_conn.close()


# --- Фікстура для тестування API (залишається без змін) ---
@pytest.fixture
def api_client():
    """Створює клієнт для тестування FastAPI ендпоінтів."""
    from fastapi.testclient import TestClient
    from bot.web_backend.main import create_web_app

    # Використовуємо patch, щоб ізолювати API-тести від бази даних
    with patch('bot.web_backend.routes.get_user_chats'), \
            patch('bot.web_backend.routes.is_group_admin'), \
            patch('bot.web_backend.routes.get_group_settings'), \
            patch('bot.web_backend.routes.set_group_setting'):
        app = create_web_app()
        client = TestClient(app)
        yield client