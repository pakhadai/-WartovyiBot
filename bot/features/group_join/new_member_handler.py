import logging
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus, ParseMode

# Зверніть увагу на зміну в імпортах
from bot.infrastructure.database import get_group_settings
from bot.infrastructure.localization import get_text
from .captcha_service import create_captcha_keyboard
from .captcha_timeout import captcha_timeout
from bot.infrastructure.database import log_action, increment_daily_stat

async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє вхід нових користувачів, враховуючи налаштування групи."""
    chat = update.chat_member.chat

    # --- ОСНОВНА ЗМІНА ---
    # Отримуємо індивідуальні налаштування для цього чату
    settings = get_group_settings(chat.id)

    if not settings['captcha_enabled']:
        return  # Виходимо, якщо CAPTCHA для цієї групи вимкнена

    old_member = update.chat_member.old_chat_member
    new_member = update.chat_member.new_chat_member

    user_was_member = old_member is not None and old_member.status not in [ChatMemberStatus.LEFT,
                                                                           ChatMemberStatus.BANNED]
    user_is_now_member = new_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]

    if not (user_is_now_member and not user_was_member):
        return

    user = new_member.user
    log_action(chat.id, user.id, 'user_joined')
    increment_daily_stat(chat.id, 'users_joined')
    lang = user.language_code or 'en'

    if user.is_bot:
        return

    logging.info(
        f"Новий користувач {user.full_name} ({user.id}) в чаті {chat.title}. Застосовуємо CAPTCHA згідно з налаштуваннями групи.")

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        reply_markup = create_captcha_keyboard(user.id)
        welcome_text = get_text(lang, "captcha_welcome", user_mention=user.mention_html())

        captcha_message = await context.bot.send_message(
            chat_id=chat.id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_notification=True
        )

        context.job_queue.run_once(
            captcha_timeout,
            120,
            data={'user_id': user.id, 'chat_id': chat.id, 'message_id': captcha_message.message_id, 'lang': lang},
            name=f"captcha_timeout_{user.id}_{chat.id}"
        )
    except Exception as e:
        logging.error(f"Помилка при обробці нового користувача {user.id} в чаті {chat.id}: {e}")