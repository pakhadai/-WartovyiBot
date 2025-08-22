# Wartovyi/bot/features/message_filtering/antiflood_service.py

import time
from telegram.ext import ContextTypes

# Константи для налаштування
FLOOD_TIME_WINDOW = 4  # Секунди, протягом яких рахуються повідомлення


def is_user_flooding(user_id: int, sensitivity: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Перевіряє, чи користувач надсилає повідомлення занадто часто.

    :param user_id: ID користувача для перевірки.
    :param sensitivity: Кількість повідомлень, яка вважається флудом.
    :param context: Контекст бота для доступу до chat_data.
    :return: True, якщо виявлено флуд, інакше False.
    """
    current_time = time.time()

    # Ініціалізуємо сховище, якщо його немає
    if 'flood_tracker' not in context.chat_data:
        context.chat_data['flood_tracker'] = {}

    user_timestamps = context.chat_data['flood_tracker'].get(user_id, [])

    # Фільтруємо старі повідомлення, залишаючи тільки ті, що в межах FLOOD_TIME_WINDOW
    recent_timestamps = [t for t in user_timestamps if current_time - t < FLOOD_TIME_WINDOW]

    # Додаємо поточний час і оновлюємо дані
    recent_timestamps.append(current_time)
    context.chat_data['flood_tracker'][user_id] = recent_timestamps

    # Перевіряємо, чи кількість недавніх повідомлень перевищує поріг
    if len(recent_timestamps) > sensitivity:
        # Якщо виявлено флуд, очищуємо історію для цього користувача,
        # щоб уникнути повторних спрацювань одразу після муту.
        context.chat_data['flood_tracker'][user_id] = []
        return True

    return False