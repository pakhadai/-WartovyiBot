import pytest
from unittest.mock import patch
from bot.features.message_filtering.antispam_service import calculate_spam_score


@pytest.mark.asyncio
@patch('bot.features.message_filtering.antispam_service.get_group_settings')
@patch('bot.features.message_filtering.antispam_service.get_group_whitelist')
@patch('bot.features.message_filtering.antispam_service.get_spam_triggers')
@patch('bot.features.message_filtering.antispam_service.get_group_blocklist')
async def test_spam_score_calculation(
        mock_get_group_blocklist,
        mock_get_spam_triggers,
        mock_get_group_whitelist,
        mock_get_group_settings
):
    """
    Тест для перевірки логіки підрахунку спам-балів.
    """
    # Arrange: Налаштовуємо моки - що мають повертати наші імітовані функції
    chat_id = -1001
    mock_get_group_settings.return_value = {
        'spam_threshold': 10, 'captcha_enabled': True, 'spam_filter_enabled': True,
        'use_global_list': True, 'use_custom_list': True
    }
    mock_get_group_whitelist.return_value = ["білеслово"]
    mock_get_spam_triggers.return_value = {"глобальний": 5, "спам": 8}
    mock_get_group_blocklist.return_value = {"локальний": 10}

    # --- Test Case 1: Whitelisted word ---
    score, triggers = calculate_spam_score("Привіт, це білеслово.", chat_id)
    assert score == 0
    assert "whitelist" in triggers[0]

    # --- Test Case 2: Global and local triggers ---
    message = "Це глобальний і локальний спам."
    score, triggers = calculate_spam_score(message, chat_id)
    # Очікуємо 5 (глобальний) + 10 (локальний) + 8 (спам)
    assert score == 5 + 10 + 8
    assert len(triggers) == 3

    # --- Test Case 3: CAPS Lock and links ---
    # Повідомлення, яке точно пройде перевірку (більше 80% великих літер)
    message = "КУПЛЮ ГАРАЖ СРОЧНО T.ME/LINK"
    score, triggers = calculate_spam_score(message, chat_id)

    # Очікуємо 5 (КАПС) + 3 (посилання)
    assert score == 8
    # Додамо більш точні перевірки, щоб бачити, які тригери спрацювали
    assert "КАПС (+5)" in triggers
    assert "посилання x1 (+3)" in triggers