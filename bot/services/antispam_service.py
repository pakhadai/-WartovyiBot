# bot/services/antispam_service.py
import re
from bot.infrastructure.database import get_spam_triggers

def calculate_spam_score(message: str, user_is_new: bool) -> (int, list):
    """Підраховує рейтинг спаму для повідомлення."""
    text = message.lower()
    spam_score = 0
    triggered_words = []

    # 1. Тригери з бази
    spam_triggers = get_spam_triggers()
    for trigger, score in spam_triggers.items():
        if trigger in text:
            spam_score += score
            triggered_words.append(f"'{trigger}' ({score})")

    # 2. Посилання
    url_pattern = r'(https?://|www\.|t\.me/|@)[^\s]+'
    urls = re.findall(url_pattern, text)
    if urls:
        spam_score += len(urls) * 3
        triggered_words.append(f"посилання x{len(urls)} (+{len(urls) * 3})")

    # ... (інші перевірки: згадки, КАПС, емодзі, повторення) ...

    # 7. Новий користувач
    if user_is_new:
        spam_score += 2
        triggered_words.append("новий користувач (+2)")

    return spam_score, triggered_words