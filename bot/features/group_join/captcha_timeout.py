import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.infrastructure.localization import get_text


async def captcha_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Обробляє таймаут капчі, видаляючи користувача."""
    job_data = context.job.data
    user_id = job_data['user_id']
    chat_id = job_data['chat_id']
    message_id = job_data['message_id']
    lang = job_data.get('lang', 'en')

    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id, until_date=None)
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)

        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)

        await context.bot.send_message(
            chat_id=chat_id,
            text=get_text(lang, "captcha_timeout_kick"),
            parse_mode=ParseMode.HTML
        )

        if 'captcha_answers' in context.chat_data and user_id in context.chat_data['captcha_answers']:
            del context.chat_data['captcha_answers'][user_id]

    except Exception as e:
        logging.error(f"Помилка при обробці таймауту капчі: {e}")