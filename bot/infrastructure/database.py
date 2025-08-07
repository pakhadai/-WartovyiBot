import datetime
import logging
import sqlite3
from bot.config import DB_NAME, ADMIN_ID


def setup_database():

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

    setup_stats_tables(conn, cursor)

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


# --- Функції для керування ГЛОБАЛЬНИМИ списками спам-слів ---

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


# --- Функції для керування ЛОКАЛЬНИМИ списками груп ---

def get_group_blocklist(group_id: int) -> dict:
    """Отримує ЛОКАЛЬНИЙ чорний список для групи."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT trigger, score FROM group_spam_triggers WHERE group_id = ?", (group_id,))
    triggers = {row['trigger']: row['score'] for row in cursor.fetchall()}
    conn.close()
    return triggers


def add_group_spam_trigger(group_id: int, trigger: str, score: int):
    """Додає слово в ЛОКАЛЬНИЙ чорний список групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO group_spam_triggers (group_id, trigger, score) VALUES (?, ?, ?)",
                   (group_id, trigger.lower(), score))
    conn.commit()
    conn.close()


def delete_group_spam_trigger(group_id: int, trigger: str):
    """Видаляє слово з ЛОКАЛЬНОГО чорного списку групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_spam_triggers WHERE group_id = ? AND trigger = ?",
                   (group_id, trigger.lower()))
    conn.commit()
    conn.close()


def get_group_whitelist(group_id: int) -> list:
    """Отримує ЛОКАЛЬНИЙ білий список для групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT trigger FROM group_whitelists WHERE group_id = ?", (group_id,))
    triggers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return triggers


def add_group_whitelist_word(group_id: int, word: str):
    """Додає слово в ЛОКАЛЬНИЙ білий список групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO group_whitelists (group_id, trigger) VALUES (?, ?)",
                   (group_id, word.lower()))
    conn.commit()
    conn.close()


def delete_group_whitelist_word(group_id: int, word: str):
    """Видаляє слово з ЛОКАЛЬНОГО білого списку групи."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_whitelists WHERE group_id = ? AND trigger = ?",
                   (group_id, word.lower()))
    conn.commit()
    conn.close()


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


def reset_warnings(user_id: int, chat_id: int):
    """Скидає попередження для користувача в конкретному чаті."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warnings WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    conn.commit()
    conn.close()


# Замініть функцію setup_stats_tables() в bot/infrastructure/database.py на цю:

def setup_stats_tables(conn=None, cursor=None):
    """Створює таблиці для збору статистики."""
    # Якщо conn і cursor не передані, створюємо власні
    close_connection = False
    if conn is None:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        close_connection = True

    # Таблиця для логування всіх дій
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            action_type TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблиця для щоденної статистики
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            group_id INTEGER,
            date DATE,
            messages_total INTEGER DEFAULT 0,
            messages_deleted INTEGER DEFAULT 0,
            users_joined INTEGER DEFAULT 0,
            users_left INTEGER DEFAULT 0,
            captcha_passed INTEGER DEFAULT 0,
            captcha_failed INTEGER DEFAULT 0,
            warnings_given INTEGER DEFAULT 0,
            bans_given INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, date)
        )
    """)

    if close_connection:
        conn.commit()
        conn.close()


def log_action(group_id: int, user_id: int, action_type: str, details: str = None):
    """Логує дію для статистики."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO action_logs (group_id, user_id, action_type, details) VALUES (?, ?, ?, ?)",
        (group_id, user_id, action_type, details)
    )
    conn.commit()
    conn.close()


def increment_daily_stat(group_id: int, stat_field: str, increment: int = 1):
    """Збільшує лічильник денної статистики."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = datetime.date.today()

    # Створюємо запис для сьогодні, якщо його немає
    cursor.execute(
        "INSERT OR IGNORE INTO daily_stats (group_id, date) VALUES (?, ?)",
        (group_id, today)
    )

    # Збільшуємо лічильник
    cursor.execute(
        f"UPDATE daily_stats SET {stat_field} = {stat_field} + ? WHERE group_id = ? AND date = ?",
        (increment, group_id, today)
    )
    conn.commit()
    conn.close()


def get_group_stats(group_id: int, days: int = 30) -> dict:
    """Отримує статистику для групи за останні N днів."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Загальна статистика
    cursor.execute("""
        SELECT 
            SUM(messages_total) as total_messages,
            SUM(messages_deleted) as total_deleted,
            SUM(users_joined) as total_joined,
            SUM(users_left) as total_left,
            SUM(captcha_passed) as total_captcha_passed,
            SUM(captcha_failed) as total_captcha_failed,
            SUM(warnings_given) as total_warnings,
            SUM(bans_given) as total_bans
        FROM daily_stats 
        WHERE group_id = ? AND date >= date('now', '-' || ? || ' days')
    """, (group_id, days))

    totals = cursor.fetchone()

    # Щоденна статистика для графіків
    cursor.execute("""
        SELECT date, messages_total, messages_deleted, users_joined, users_left
        FROM daily_stats 
        WHERE group_id = ? AND date >= date('now', '-' || ? || ' days')
        ORDER BY date
    """, (group_id, days))

    daily_data = cursor.fetchall()

    # Топ порушників
    cursor.execute("""
        SELECT user_id, COUNT(*) as violation_count
        FROM action_logs
        WHERE group_id = ? 
            AND action_type IN ('spam_detected', 'warning_given', 'user_banned')
            AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
        GROUP BY user_id
        ORDER BY violation_count DESC
        LIMIT 5
    """, (group_id, days))

    top_violators = cursor.fetchall()

    # Активність по годинах
    cursor.execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM action_logs
        WHERE group_id = ? 
            AND action_type = 'message_sent'
            AND datetime(timestamp) >= datetime('now', '-7 days')
        GROUP BY hour
        ORDER BY hour
    """, (group_id,))

    hourly_activity = cursor.fetchall()

    conn.close()

    return {
        'totals': dict(totals) if totals else {},
        'daily': [dict(row) for row in daily_data],
        'top_violators': [dict(row) for row in top_violators],
        'hourly_activity': [dict(row) for row in hourly_activity]
    }


def get_group_current_stats(group_id: int) -> dict:
    """Отримує поточну статистику групи (користувачі з попередженнями тощо)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Кількість користувачів з попередженнями
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) as users_with_warnings,
               SUM(warning_count) as total_warnings
        FROM warnings
        WHERE chat_id = ? AND warning_count > 0
    """, (group_id,))

    warnings_data = cursor.fetchone()

    # Налаштування групи
    cursor.execute("""
        SELECT captcha_enabled, spam_filter_enabled, spam_threshold, 
               use_global_list, use_custom_list
        FROM group_settings
        WHERE group_id = ?
    """, (group_id,))

    settings = cursor.fetchone()

    # Кількість слів у локальних списках
    cursor.execute("SELECT COUNT(*) as count FROM group_spam_triggers WHERE group_id = ?", (group_id,))
    blocklist_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM group_whitelists WHERE group_id = ?", (group_id,))
    whitelist_count = cursor.fetchone()['count']

    conn.close()

    return {
        'warnings': dict(warnings_data) if warnings_data else {},
        'settings': dict(settings) if settings else {},
        'blocklist_count': blocklist_count,
        'whitelist_count': whitelist_count
    }
