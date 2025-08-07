import logging
import sqlite3
from bot.config import DB_NAME, ADMIN_ID


def setup_database():
    """
    Створює та налаштовує всі необхідні таблиці в базі даних.
    Виконує міграції, додаючи нові стовпці до існуючих таблиць.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- Основні таблиці ---
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER, chat_id INTEGER, warning_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, chat_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    # --- Таблиці для триярусної логіки спам-фільтра ---
    cursor.execute("CREATE TABLE IF NOT EXISTS spam_triggers (trigger TEXT PRIMARY KEY, score INTEGER NOT NULL)")
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS group_spam_triggers (group_id INTEGER, trigger TEXT, score INTEGER, PRIMARY KEY (group_id, trigger))")
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS group_whitelists (group_id INTEGER, trigger TEXT, PRIMARY KEY (group_id, trigger))")
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS suggested_triggers (trigger TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 1, added_by INTEGER)")

    # --- Таблиці для мульти-власників ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY, group_name TEXT, spam_threshold INTEGER DEFAULT 10,
            captcha_enabled INTEGER DEFAULT 1, spam_filter_enabled INTEGER DEFAULT 1,
            use_global_list INTEGER DEFAULT 1, use_custom_list INTEGER DEFAULT 1
        )
    """)
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS group_admins (group_id INTEGER, user_id INTEGER, PRIMARY KEY (group_id, user_id))")

    # --- Безпечне додавання нових стовпців (Міграція) ---
    try:
        cursor.execute("ALTER TABLE group_settings ADD COLUMN use_global_list INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE group_settings ADD COLUMN use_custom_list INTEGER DEFAULT 1")
        logging.info("Міграція БД: Додано стовпці 'use_global_list' та 'use_custom_list'.")
    except sqlite3.OperationalError:
        pass

    # --- Заповнення початковими даними ---
    default_settings = {"spam_threshold": "10", "captcha_enabled": "1", "spam_filter_enabled": "1"}
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    initial_triggers = {
        "пиши в лс": 8, "пишите в лс": 8, "в лс": 5, "заработке": 4, "заработок": 4,
        "без вложений": 7, "крипта": 6, "криптовалюта": 6, "binance": 5, "арбитраж": 8,
        "p2p": 7, "ищу людей": 6, "пассивный доход": 6, "пропоную роботу": 7,
        "легкие деньги": 9, "схема заработка": 10
    }
    cursor.executemany("INSERT OR IGNORE INTO spam_triggers (trigger, score) VALUES (?, ?)", initial_triggers.items())

    conn.commit()
    conn.close()
    logging.info(f"База даних '{DB_NAME}' успішно налаштована та оновлена.")


# --- Функції для керування налаштуваннями ---

def get_global_settings() -> dict:
    """Отримує глобальні налаштування бота з таблиці 'settings'."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings_db = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()

    return {
        'spam_threshold': int(settings_db.get('spam_threshold', 10)),
        'captcha_enabled': bool(int(settings_db.get('captcha_enabled', 1))),
        'spam_filter_enabled': bool(int(settings_db.get('spam_filter_enabled', 1))),
        'use_global_list': True,
        'use_custom_list': False,
    }


def set_global_setting(key: str, value):
    """Встановлює глобальне налаштування в таблиці 'settings'."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if isinstance(value, bool):
        value = "1" if value else "0"
    cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_group_settings(group_id: int) -> dict:
    """Отримує налаштування для конкретної групи."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM group_settings WHERE group_id = ?", (group_id,))
    settings_db = cursor.fetchone()
    conn.close()

    if settings_db:
        return {
            'spam_threshold': int(settings_db['spam_threshold']),
            'captcha_enabled': bool(settings_db['captcha_enabled']),
            'spam_filter_enabled': bool(settings_db['spam_filter_enabled']),
            'use_global_list': bool(settings_db['use_global_list']),
            'use_custom_list': bool(settings_db['use_custom_list']),
        }
    return get_global_settings()


def set_group_setting(group_id: int, key: str, value):
    """Встановлює налаштування для конкретної групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if isinstance(value, bool): value = 1 if value else 0
    cursor.execute(f"UPDATE group_settings SET {key} = ? WHERE group_id = ?", (value, group_id))
    conn.commit()
    conn.close()


# --- Функції для мульти-власників ---

def add_group_if_not_exists(group_id: int, group_name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO group_settings (group_id, group_name) VALUES (?, ?)", (group_id, group_name))
    conn.commit()
    conn.close()


def set_group_admin(group_id: int, user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_admins WHERE group_id = ?", (group_id,))
    cursor.execute("INSERT INTO group_admins (group_id, user_id) VALUES (?, ?)", (group_id, user_id))
    conn.commit()
    conn.close()


def is_group_admin(user_id: int, group_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM group_admins WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_user_chats(user_id: int) -> list:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if user_id == ADMIN_ID:
        cursor.execute("SELECT group_id, group_name FROM group_settings ORDER BY group_name")
    else:
        cursor.execute("""
            SELECT gs.group_id, gs.group_name 
            FROM group_settings gs
            JOIN group_admins ga ON gs.group_id = ga.group_id
            WHERE ga.user_id = ?
            ORDER BY gs.group_name
        """, (user_id,))
    chats = [{"id": row['group_id'], "name": row['group_name']} for row in cursor.fetchall()]
    conn.close()
    return chats


def get_group_admin_id(group_id: int) -> int or None:
    """Знаходить ID адміна бота для конкретної групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM group_admins WHERE group_id = ?", (group_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# --- Функції для керування списками спам-слів ---

def get_spam_triggers() -> dict:
    """Отримує ГЛОБАЛЬНИЙ список спам-слів."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT trigger, score FROM spam_triggers")
    triggers = {row['trigger']: row['score'] for row in cursor.fetchall()}
    conn.close()
    return triggers


def add_spam_trigger(trigger: str, score: int):
    """Додає слово в ГЛОБАЛЬНИЙ список."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO spam_triggers (trigger, score) VALUES (?, ?)", (trigger.lower(), score))
    conn.commit()
    conn.close()


def delete_spam_trigger(trigger: str):
    """Видаляє слово з ГЛОБАЛЬНОГО списку."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM spam_triggers WHERE trigger = ?", (trigger.lower(),))
    conn.commit()
    conn.close()


def get_group_blocklist(group_id: int) -> dict:
    """Отримує ЛОКАЛЬНИЙ чорний список для групи."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT trigger, score FROM group_spam_triggers WHERE group_id = ?", (group_id,))
    triggers = {row['trigger']: row['score'] for row in cursor.fetchall()}
    conn.close()
    return triggers


def get_group_whitelist(group_id: int) -> list:
    """Отримує ЛОКАЛЬНИЙ білий список для групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT trigger FROM group_whitelists WHERE group_id = ?", (group_id,))
    triggers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return triggers


# --- Інші функції ---

def add_warning(user_id: int, chat_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT warning_count FROM warnings WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    result = cursor.fetchone()
    new_count = (result[0] + 1) if result else 1
    cursor.execute("REPLACE INTO warnings (user_id, chat_id, warning_count) VALUES (?, ?, ?)",
                   (user_id, chat_id, new_count))
    conn.commit()
    conn.close()
    return new_count
