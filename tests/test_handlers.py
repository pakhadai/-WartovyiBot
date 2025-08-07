import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Тестування обробників (Handlers) ---

@pytest.mark.asyncio
async def test_start_handler():
    """Перевіряє, що команда /start викликає відповідь з правильним текстом."""
    from bot.features.common_commands.start_handler import start
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    update.effective_user.language_code = 'uk'
    await start(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args
    assert "Привіт" in call_args.args[0]


@pytest.mark.asyncio
@patch('bot.features.group_join.new_member_handler.get_group_settings')
# Додаємо фікстуру test_db
async def test_new_member_handler_captcha_enabled(mock_get_settings, test_db):
    """
    Перевіряє, що для нового учасника створюється CAPTCHA.
    """
    from bot.features.group_join.new_member_handler import new_member_handler
    mock_get_settings.return_value = {'captcha_enabled': True}

    update = MagicMock()
    # Встановлюємо реальні числові ID
    update.chat_member.chat.id = -10012345
    update.chat_member.new_chat_member.user.id = 54321
    update.chat_member.new_chat_member.user.is_bot = False
    update.chat_member.new_chat_member.user.language_code = 'uk'
    update.chat_member.new_chat_member.status = 'member'
    update.chat_member.old_chat_member.status = 'left'

    context = MagicMock()
    context.bot.restrict_chat_member = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.job_queue.run_once = MagicMock()

    await new_member_handler(update, context)

    context.bot.restrict_chat_member.assert_called_once()
    context.bot.send_message.assert_called_once()
    context.job_queue.run_once.assert_called_once()
    call_args = context.bot.send_message.call_args
    assert "верифікація" in call_args.kwargs['text']


@pytest.mark.asyncio
# Додаємо новий патч для get_group_admin_id
@patch('bot.features.message_filtering.message_handler.get_group_admin_id')
@patch('bot.features.message_filtering.message_handler.get_group_settings')
@patch('bot.features.message_filtering.message_handler.calculate_spam_score')
@patch('bot.features.message_filtering.message_handler.add_warning')
async def test_message_handler_deletes_spam(
        mock_add_warning, mock_calc_score, mock_get_settings, mock_get_admin_id, test_db
):
    """
    Перевіряє, що обробник повідомлень видаляє спам, надсилає попередження і лог.
    """
    from bot.features.message_filtering.message_handler import message_handler

    # 1. Arrange
    mock_get_settings.return_value = {'spam_filter_enabled': True, 'spam_threshold': 10}
    mock_calc_score.return_value = (15, ["'спам' (15)"])
    mock_add_warning.return_value = 1
    # Імітуємо, що для цього чату є локальний адмін з ID 999
    mock_get_admin_id.return_value = 999

    update = MagicMock()
    update.message.chat.id = -10012345
    # Додаємо назву чату, бо вона використовується в лозі
    update.message.chat.title = "Тестовий Чат"
    update.message.from_user.id = 54321
    update.message.from_user.language_code = 'uk'  # Додаємо мову для коректних логів
    update.message.text = "це спам"
    update.message.delete = AsyncMock()

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.restrict_chat_member = AsyncMock()
    context.job_queue.run_once = MagicMock()

    # 2. Act
    await message_handler(update, context)

    # 3. Assert
    update.message.delete.assert_called_once()
    context.bot.restrict_chat_member.assert_called_once()

    # Очікуємо, що send_message було викликано рівно 2 рази
    assert context.bot.send_message.call_count == 2

    # Перевіряємо перший виклик - попередження в групу
    first_call_args = context.bot.send_message.call_args_list[0]
    assert first_call_args.kwargs['chat_id'] == -10012345
    assert "ваше повідомлення видалено" in first_call_args.kwargs['text'].lower()

    # Перевіряємо другий виклик - лог адміну
    second_call_args = context.bot.send_message.call_args_list[1]
    assert second_call_args.kwargs['chat_id'] == 999  # Перевіряємо, що лог іде адміну
    assert "СПАМ ВИЯВЛЕНО" in second_call_args.kwargs['text']