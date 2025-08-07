import pytest
from bot.infrastructure.database import (
    add_spam_trigger,
    get_spam_triggers,
    add_group_if_not_exists,
    get_user_chats
)


# Використовуємо фікстуру test_db, щоб тест працював з чистою БД
def test_add_and_get_spam_trigger(test_db):
    """
    Тест перевіряє, чи можна додати і отримати глобальний спам-тригер.
    """
    # Arrange: готуємо дані
    trigger = "тестове слово"
    score = 15

    # Act: виконуємо дію
    add_spam_trigger(trigger, score)

    # Assert: перевіряємо результат
    triggers = get_spam_triggers()
    assert trigger in triggers
    assert triggers[trigger] == score


def test_add_group_and_get_chats(test_db):
    """
    Тест перевіряє, чи додається група і чи може користувач її отримати.
    """
    # Arrange
    group_id = -100123456
    group_name = "Тестова Група"
    user_id = 12345

    # Act
    add_group_if_not_exists(group_id, group_name)
    # Поки що немає функції для призначення адміна, тому перевіримо для глобального
    from bot.infrastructure.database import set_group_admin
    set_group_admin(group_id, user_id)

    # Assert
    user_chats = get_user_chats(user_id)
    assert len(user_chats) == 1
    assert user_chats[0]['id'] == group_id
    assert user_chats[0]['name'] == group_name