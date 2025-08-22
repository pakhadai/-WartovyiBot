# Wartovyi/bot/features/message_filtering/message_handler.py

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Імпортуємо всі необхідні функції з ваших модулів
from bot.infrastructure.database import increment_daily_stat, log_action, get_group_settings, add_warning, \
    get_group_admin_id, get_punishment_settings
from bot.config import ADMIN_ID
from bot.infrastructure.localization import get_text
from .antispam_service import calculate_spam_score
from .delete_message_job import delete_message_job
from .antiflood_service import is_user_flooding


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробляє текстові повідомлення, викликаючи оновлений antispam_service
    з урахуванням індивідуальних налаштувань групи, анти-флуду та гнучких покарань.
    """
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat = update.message.chat
    settings = get_group_settings(chat.id)

    # --- ПЕРЕВІРКА НА ФЛУД ---
    if settings.get('antiflood_enabled', True):
        if is_user_flooding(user.id, settings.get('antiflood_sensitivity', 5), context):
            try:
                # Видаємо мут на 5 хвилин
                mute_duration = datetime.now() + timedelta(minutes=5)
                await context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_duration
                )

                # Надсилаємо попередження (поки що без перекладу, додамо пізніше)
                warning_msg = await update.message.reply_text(
                    f"⚠️ {user.mention_html()}, ви надсилаєте повідомлення занадто часто!\n"
                    f"📵 Мут на 5 хвилин.",
                    parse_mode=ParseMode.HTML
                )

                # Видаляємо повідомлення, що спричинило флуд
                await update.message.delete()

                # Ставимо завдання на видалення попередження через 30 секунд
                context.job_queue.run_once(
                    delete_message_job, 30,
                    data={'chat_id': chat.id, 'message_id': warning_msg.message_id}
                )

                # Логуємо дію
                log_action(chat.id, user.id, user.full_name, 'antiflood_triggered', 'Muted for 5 minutes')

            except Exception as e:
                logging.error(f"Помилка під час обробки флуду від {user.id} в чаті {chat.id}: {e}")

            # Важливо: припиняємо подальшу обробку повідомлення
            return
    # --- КІНЕЦЬ ПЕРЕВІРКИ НА ФЛУД ---

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

        # 1. Найвища пріоритетна дія - видалення повідомлення. Виконуємо її негайно.
        try:
            await update.message.delete()
        except Exception as e:
            logging.warning(f"Не вдалося видалити повідомлення {update.message.id} в чаті {chat.id}: {e}")

        # 2. Всі інші дії (покарання, сповіщення, лог) збираємо в список
        #    і запускаємо паралельно за допомогою asyncio.gather.

        warnings_count = add_warning(user.id, chat.id)
        lang = user.language_code

        # --- НОВА ЛОГІКА ГНУЧКИХ ПОКАРАНЬ ---
        punishment_rules = get_punishment_settings(chat.id)
        # Визначаємо правило для поточного рівня попереджень,
        # якщо для цього рівня правила немає, беремо правило для максимального налаштованого рівня
        rule_key = warnings_count if warnings_count in punishment_rules else max(punishment_rules.keys())
        rule = punishment_rules.get(rule_key)

        action_taken_log = "Невідомо"
        warning_text = ""
        tasks_to_run = []

        try:
            if rule and rule.get('action') == "mute":
                mute_duration_minutes = rule['duration']
                mute_until = datetime.now() + timedelta(minutes=mute_duration_minutes)
                tasks_to_run.append(context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                ))
                # TODO: Додати нові тексти для гнучких покарань
                warning_text = f"⚠️ {user.mention_html()}, ваше повідомлення видалено за спам.\n📵 Мут на {mute_duration_minutes} хвилин."
                action_taken_log = f"Мут на {mute_duration_minutes} хв."

            elif rule and rule.get('action') == "ban":
                tasks_to_run.append(context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id))
                warning_text = get_text(lang, "spam_warning_3",
                                        user_mention=user.mention_html())  # Використовуємо старий текст про бан
                action_taken_log = "Бан"

            # Надсилаємо повідомлення про покарання в чат
            if warning_text:
                warning_msg_task = context.bot.send_message(
                    chat_id=chat.id, text=warning_text, parse_mode=ParseMode.HTML, disable_notification=True
                )
                tasks_to_run.append(warning_msg_task)

        except Exception as e:
            logging.error(f"Помилка при підготовці покарання для {user.id} в чаті {chat.id}: {e}")
        # --- КІНЕЦЬ НОВОЇ ЛОГІКИ ---

        # Підготовка завдання для логування власнику
        log_recipient_id = group_admin_id or ADMIN_ID
        try:
            log_message = get_text(
                "uk",  # Логи завжди однією мовою для уніфікації
                "log_spam_detected",
                user_mention=user.mention_html(),
                user_id=user.id,
                chat_title=chat.title,
                spam_score=spam_score,
                threshold=settings['spam_threshold'],
                triggered_words=', '.join(triggered_words),
                warnings_count=warnings_count,
                action_taken=action_taken_log,
                message_text=update.message.text
            )
            # Тут можна додати клавіатуру для логів, якщо вона потрібна
            log_keyboard = None
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
            elif hasattr(result, 'message_id') and result.chat_id == chat.id:
                context.job_queue.run_once(
                    delete_message_job, 30, data={'chat_id': result.chat_id, 'message_id': result.message_id}
                )

        # Синхронні дії, що залишилися
        log_action(chat.id, user.id, user.full_name, 'spam_detected', f'Score: {spam_score}')
        increment_daily_stat(chat.id, 'messages_deleted')