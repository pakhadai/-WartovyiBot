import pytest
import importlib
from unittest.mock import patch


# Прибираємо фікстуру clear_localization_cache
# Вона більше не потрібна

def test_get_existing_translation(monkeypatch):
    """Перевіряє отримання існуючого ключа для мови."""
    # Імпортуємо модуль прямо тут
    from bot.infrastructure import localization
    # Перезавантажуємо його, щоб скинути будь-який кеш
    importlib.reload(localization)

    # Тепер патчимо функцію, яку він використовує всередині
    monkeypatch.setattr(localization, "load_translation_file",
                        lambda lang: {"start": f"Привіт з {lang}"})

    text = localization.get_text("uk", "start")
    assert text == "Привіт з uk"


def test_fallback_language(monkeypatch):
    """Перевіряє, що використовується запасна мова."""
    from bot.infrastructure import localization
    importlib.reload(localization)

    def mock_exists(path):
        return "en.json" in path  # Тільки англійський файл "існує"

    monkeypatch.setattr("os.path.exists", mock_exists)
    monkeypatch.setattr(localization, "load_translation_file",
                        lambda lang: {"start": f"Hello from {lang}"})

    text = localization.get_text("de-DE", "start")
    assert text == "Hello from en"


def test_translation_with_formatting(monkeypatch):
    """Перевіряє форматування рядків."""
    from bot.infrastructure import localization
    importlib.reload(localization)

    monkeypatch.setattr("os.path.exists", lambda path: True)
    monkeypatch.setattr(localization, "load_translation_file",
                        lambda lang: {"captcha_welcome": "Ласкаво просимо, {user_mention}!"})

    text = localization.get_text("uk", "captcha_welcome", user_mention="Дмитро")
    assert text == "Ласкаво просимо, Дмитро!"


def test_key_not_found():
    """Перевіряє поведінку, якщо ключ не знайдено."""
    from bot.infrastructure import localization
    importlib.reload(localization)

    text = localization.get_text("uk", "non_existent_key_12345")
    assert text == "KEY_NOT_FOUND: non_existent_key_12345"