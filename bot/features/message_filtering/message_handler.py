import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
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
    settings = get_group_settings(chat.id)

    # Синхронна частина - виконується першою
    increment_daily_stat(chat.id, 'messages_total')
    if not settings['spam_filter_enabled']:
        return

    group_admin_id = get_group_admin_id(chat.id)
    if user.id == ADMIN_ID or user.id == group_admin_id:
        return

    spam_score, triggered_words = calculate_spam_score(update.message.text, chat.id)
    if "whitelist" in (triggered_words[0] if triggered_words else ""):
        return

    if spam_score >= settings['spam_threshold']:
        logging.info(f"Виявлено спам від {user.full_name} ({user.id}) з рахунком {spam_score} в чаті {chat.title}")

        # --- ОПТИМІЗАЦІЯ ---
        # 1. Найвища пріоритетна дія - видалення повідомлення. Виконуємо її негайно.
        try:
            await update.message.delete()
        except Exception as e:
            logging.warning(f"Не вдалося видалити повідомлення {update.message.id} в чаті {chat.id}: {e}")

        # 2. Всі інші дії (покарання, сповіщення, лог) збираємо в список
        #    і запускаємо паралельно за допомогою asyncio.gather.

        warnings_count = add_warning(user.id, chat.id)
        lang = user.language_code
        action_taken_log = ""
        warning_text = ""

        tasks_to_run = []

        # Підготовка завдань для покарання та сповіщення
        try:
            if warnings_count == 1:
                mute_duration = datetime.now() + timedelta(days=1)
                tasks_to_run.append(context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_duration
                ))
                warning_text = get_text(lang, "spam_warning_1", user_mention=user.mention_html())
                action_taken_log = "Мут на 1 день"
            elif warnings_count == 2:
                mute_duration = datetime.now() + timedelta(days=7)
                tasks_to_run.append(context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_duration
                ))
                warning_text = get_text(lang, "spam_warning_2", user_mention=user.mention_html())
                action_taken_log = "Мут на 7 днів"
            else:
                tasks_to_run.append(context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id))
                warning_text = get_text(lang, "spam_warning_3", user_mention=user.mention_html())
                action_taken_log = "Бан"

            warning_msg_task = context.bot.send_message(
                chat_id=chat.id, text=warning_text, parse_mode=ParseMode.HTML, disable_notification=True
            )
            tasks_to_run.append(warning_msg_task)

        except Exception as e:
            logging.error(f"Помилка при підготовці покарання для {user.id} в чаті {chat.id}: {e}")

        # Підготовка завдання для логування
        log_recipient_id = group_admin_id or ADMIN_ID
        try:
            # ... (код для створення log_keyboard та log_message залишається той самий)
            log_keyboard = ...
            log_message = ...
            tasks_to_run.append(context.bot.send_message(
                chat_id=log_recipient_id, text=log_message,
                parse_mode=ParseMode.HTML, reply_markup=log_keyboard
            ))
        except Exception as e:
            logging.error(f"Не вдалося підготувати лог власнику {log_recipient_id} для чату {chat.id}: {e}")

        # Запускаємо всі підготовлені завдання паралельно
        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

        # Обробляємо результати, щоб запланувати видалення повідомлення-попередження
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Помилка при виконанні фонового завдання: {result}")
            # Шукаємо результат від `warning_msg_task`
            elif hasattr(result, 'message_id') and tasks_to_run[
                i].__name__ == 'send_message' and result.chat_id == chat.id:
                context.job_queue.run_once(
                    delete_message_job, 30, data={'chat_id': result.chat_id, 'message_id': result.message_id}
                )

        # Синхронні дії, що залишилися
        log_action(chat.id, user.id, 'spam_detected', f'Score: {spam_score}')
        increment_daily_stat(chat.id, 'messages_deleted')
