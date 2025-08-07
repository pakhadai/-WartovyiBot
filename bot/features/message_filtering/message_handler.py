import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.infrastructure.database import increment_daily_stat, log_action
from bot.config import ADMIN_ID
from bot.infrastructure.database import get_group_settings, add_warning, get_group_admin_id
from bot.infrastructure.localization import get_text
from .antispam_service import calculate_spam_score
from .delete_message_job import delete_message_job


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробляє текстові повідомлення, викликаючи оновлений antispam_service
    з урахуванням індивідуальних налаштувань групи.
    """
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat = update.message.chat

    increment_daily_stat(chat.id, 'messages_total')

    settings = get_group_settings(chat.id)

    if not settings['spam_filter_enabled']:
        return

    group_admin_id = get_group_admin_id(chat.id)
    if user.id == ADMIN_ID or user.id == group_admin_id:
        return

    # --- ОСНОВНА ЗМІНА: ПЕРЕДАЄМО chat.id В СЕРВІС ---
    spam_score, triggered_words = calculate_spam_score(update.message.text, chat.id)

    if triggered_words and "whitelist" in triggered_words[0]:
        logging.info(
            f"Повідомлення від {user.full_name} в чаті {chat.title} пропущено через білий список: {triggered_words[0]}")
        return

    if spam_score >= settings['spam_threshold']:
        logging.info(f"Виявлено спам від {user.full_name} ({user.id}) з рахунком {spam_score} в чаті {chat.title}")

        try:
            await update.message.delete()
        except Exception as e:
            logging.warning(f"Не вдалося видалити повідомлення {update.message.id} в чаті {chat.id}: {e}")

        log_action(chat.id, user.id, 'spam_detected', f'Score: {spam_score}')
        increment_daily_stat(chat.id, 'messages_deleted')

        warnings_count = add_warning(user.id, chat.id)
        lang = user.language_code
        action_taken_log = ""
        warning_text = ""

        try:
            if warnings_count == 1:
                mute_duration = datetime.now() + timedelta(days=1)
                await context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_duration
                )
                warning_text = get_text(lang, "spam_warning_1", user_mention=user.mention_html())
                action_taken_log = "Мут на 1 день"
                increment_daily_stat(chat.id, 'warnings_given')
                log_action(chat.id, user.id, 'warning_given', f'Warning #1')
            elif warnings_count == 2:
                mute_duration = datetime.now() + timedelta(days=7)
                await context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_duration
                )
                warning_text = get_text(lang, "spam_warning_2", user_mention=user.mention_html())
                action_taken_log = "Мут на 7 днів"
                increment_daily_stat(chat.id, 'warnings_given')
                log_action(chat.id, user.id, 'warning_given', f'Warning #2')
            else:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
                warning_text = get_text(lang, "spam_warning_3", user_mention=user.mention_html())
                action_taken_log = "Бан"
                increment_daily_stat(chat.id, 'bans_given')
                increment_daily_stat(chat.id, 'warnings_given')
                log_action(chat.id, user.id, 'user_banned')

            warning_msg = await context.bot.send_message(
                chat_id=chat.id, text=warning_text, parse_mode=ParseMode.HTML, disable_notification=True
            )
            context.job_queue.run_once(
                delete_message_job, 30, data={'chat_id': warning_msg.chat_id, 'message_id': warning_msg.message_id}
            )

        except Exception as e:
            logging.error(f"Помилка при застосуванні покарання для {user.id} в чаті {chat.id}: {e}")

        log_recipient_id = group_admin_id or ADMIN_ID
        try:
            log_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text(lang, "log_unrestrict_button"),
                                     callback_data=f"log:unrestrict:{user.id}:{chat.id}"),
                InlineKeyboardButton(get_text(lang, "log_ban_button"), callback_data=f"log:ban:{user.id}:{chat.id}"),
                InlineKeyboardButton(get_text(lang, "log_ignore_button"),
                                     callback_data=f"log:ignore:{user.id}:{chat.id}"),
            ]])

            message_text_for_log = update.message.text[:500] + ("..." if len(update.message.text) > 500 else "")

            log_message = get_text(
                lang, "log_spam_detected",
                user_mention=user.mention_html(), user_id=user.id, chat_title=chat.title,
                spam_score=spam_score, threshold=settings['spam_threshold'],
                triggered_words=', '.join(triggered_words) if triggered_words else "немає",
                warnings_count=warnings_count,
                action_taken=action_taken_log,
                message_text=message_text_for_log
            )

            await context.bot.send_message(
                chat_id=log_recipient_id,
                text=log_message,
                parse_mode=ParseMode.HTML,
                reply_markup=log_keyboard
            )
        except Exception as e:
            logging.error(f"Не вдалося надіслати лог власнику {log_recipient_id} для чату {chat.id}: {e}")
