import re
from bot.infrastructure.database import (
    get_group_settings,
    get_spam_triggers,
    get_group_blocklist,
    get_group_whitelist
)


def calculate_spam_score(message_text: str, chat_id: int) -> (int, list):
    """
    Підраховує рейтинг спаму, використовуючи триярусну логіку
    (глобальний, локальний та білий списки) згідно з налаштуваннями групи.
    """
    text_lower = message_text.lower()
    spam_score = 0
    triggered_words = []

    # 1. Отримуємо налаштування та всі необхідні списки для цього чату
    settings = get_group_settings(chat_id)
    whitelist = get_group_whitelist(chat_id)

    # 2. Перевірка на білий список. Якщо слово у білому списку, аналіз по ньому припиняється.
    for whitelisted_word in whitelist:
        if whitelisted_word in text_lower:
            return 0, [f"'{whitelisted_word}' (whitelist)"]

    # 3. Формуємо фінальний список спам-слів згідно з налаштуваннями групи
    final_triggers = {}
    if settings.get('use_global_list', True):
        final_triggers.update(get_spam_triggers())

    if settings.get('use_custom_list', True):
        # Локальні слова мають вищий пріоритет (перезапишуть глобальні, якщо є збіги)
        final_triggers.update(get_group_blocklist(chat_id))

    # 4. Проходимо по фінальному списку тригерів
    for trigger, score in final_triggers.items():
        if trigger in text_lower:
            spam_score += score
            triggered_words.append(f"'{trigger}' ({score})")

    # 5. Аналіз за іншими критеріями (посилання, згадки, КАПС)
    url_pattern = r'(https?://|www\.|t\.me/)[^\s]+'
    if re.search(url_pattern, text_lower):
        urls_count = len(re.findall(url_pattern, text_lower))
        spam_score += urls_count * 3
        triggered_words.append(f"посилання x{urls_count} (+{urls_count * 3})")

    if len(re.findall(r'@\w+', text_lower)) > 2:
        mentions_count = len(re.findall(r'@\w+', text_lower))
        spam_score += mentions_count * 2
        triggered_words.append(f"згадки x{mentions_count} (+{mentions_count * 2})")

    if len(message_text) > 10 and (sum(1 for c in message_text if c.isupper()) / len(message_text)) > 0.7:
        spam_score += 5
        triggered_words.append("КАПС (+5)")

    return spam_score, triggered_words