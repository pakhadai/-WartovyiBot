import json
import os
from typing import Dict

# Кеш для завантажених мов, щоб не читати файли з диска кожен раз
_loaded_languages: Dict[str, Dict[str, str]] = {}

LANGUAGE_FALLBACKS = {
    'uk': ['uk', 'ru', 'en'],
    'ru': ['ru', 'uk', 'en'],
    'be': ['ru', 'uk', 'en'],
    'kk': ['ru', 'en'],
    'de': ['en'], 'fr': ['en'], 'es': ['en'], 'pl': ['en'],
}


def load_translation_file(lang_code: str) -> dict:
    """Завантажує JSON-файл перекладу для вказаної мови."""
    # Визначаємо шлях до папки з перекладами
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, f"{lang_code}.json")

    if not os.path.exists(filepath):
        # Якщо файл для мови не знайдено, повертаємо англійський
        filepath = os.path.join(current_dir, "en.json")

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_user_language(language_code: str) -> str:
    """Визначає найкращу доступну мову для користувача."""
    if not language_code:
        return 'en'
    lang = language_code.split('-')[0].lower()

    # Перевіряємо, чи існує JSON-файл для такої мови
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(current_dir, f"{lang}.json")):
        return lang

    # Шукаємо запасний варіант
    for fallback_lang in LANGUAGE_FALLBACKS.get(lang, ['en']):
        if os.path.exists(os.path.join(current_dir, f"{fallback_lang}.json")):
            return fallback_lang
    return 'en'


def get_text(lang_code: str, key: str, **kwargs) -> str:
    """Отримує локалізований текст з підтримкою fallback."""
    target_lang = get_user_language(lang_code)

    fallback_chain = LANGUAGE_FALLBACKS.get(target_lang, [target_lang, 'en'])

    for lang in fallback_chain:
        # Завантажуємо мову в кеш, якщо її там ще немає
        if lang not in _loaded_languages:
            try:
                _loaded_languages[lang] = load_translation_file(lang)
            except Exception:
                continue

        # Шукаємо ключ у завантаженій мові
        if key in _loaded_languages.get(lang, {}):
            text = _loaded_languages[lang][key]
            # Форматуємо, якщо є параметри
            if kwargs:
                try:
                    return text.format(**kwargs)
                except KeyError:
                    return text
            return text

    # Якщо ключ не знайдено ніде
    return f"KEY_NOT_FOUND: {key}"
