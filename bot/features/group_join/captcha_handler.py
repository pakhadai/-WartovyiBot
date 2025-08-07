import logging
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.infrastructure.localization import get_text
from bot.infrastructure.database import log_action, increment_daily_stat

MAX_ATTEMPTS = 2


async def captcha_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопок капчі."""
    query = update.callback_query
    user_who_clicked = query.from_user
    lang = user_who_clicked.language_code or 'en'

    try:
        _, user_id_str, chosen_emoji, correct_emoji = query.data.split(":", 3)
        user_id_for_captcha = int(user_id_str)
    except ValueError:
        await query.answer("Помилка даних", show_alert=True)
        return

    if user_who_clicked.id != user_id_for_captcha:
        await query.answer(get_text(lang, "captcha_not_for_you"), show_alert=True)
        return

    # Ініціалізуємо лічильник спроб
    if 'captcha_attempts' not in context.chat_data:
        context.chat_data['captcha_attempts'] = {}
    if user_id_for_captcha not in context.chat_data['captcha_attempts']:
        context.chat_data['captcha_attempts'][user_id_for_captcha] = 0

    if chosen_emoji == correct_emoji:
        await query.answer(get_text(lang, "captcha_verified_short"), show_alert=True)
        for job in context.job_queue.get_jobs_by_name(f"captcha_timeout_{user_id_for_captcha}_{query.message.chat.id}"):
            job.schedule_removal()

            log_action(query.message.chat.id, user_id_for_captcha, 'captcha_passed')
            increment_daily_stat(query.message.chat.id, 'captcha_passed')

        try:
            await context.bot.restrict_chat_member(
                chat_id=query.message.chat.id,
                user_id=user_id_for_captcha,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True
                )
            )
            await query.edit_message_text(
                get_text(lang, "captcha_verified", user_mention=user_who_clicked.mention_html()),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Помилка при знятті обмежень: {e}")
        finally:
            if user_id_for_captcha in context.chat_data['captcha_attempts']:
                del context.chat_data['captcha_attempts'][user_id_for_captcha]
    else:
        context.chat_data['captcha_attempts'][user_id_for_captcha] += 1
        attempts = context.chat_data['captcha_attempts'][user_id_for_captcha]

        if attempts >= MAX_ATTEMPTS:
            await query.answer(get_text(lang, "captcha_too_many_attempts"), show_alert=True)
            for job in context.job_queue.get_jobs_by_name(
                    f"captcha_timeout_{user_id_for_captcha}_{query.message.chat.id}"):
                job.schedule_removal()

                log_action(query.message.chat.id, user_id_for_captcha, 'captcha_failed')
                increment_daily_stat(query.message.chat.id, 'captcha_failed')

            try:
                await query.edit_message_text(get_text(lang, "captcha_fail_kick"))
                await context.bot.ban_chat_member(chat_id=query.message.chat.id, user_id=user_id_for_captcha,
                                                  until_date=None)
                await context.bot.unban_chat_member(chat_id=query.message.chat.id, user_id=user_id_for_captcha)
            except Exception as e:
                logging.error(f"Помилка при кіку користувача: {e}")
            finally:
                if user_id_for_captcha in context.chat_data['captcha_attempts']:
                    del context.chat_data['captcha_attempts'][user_id_for_captcha]
        else:
            attempts_left = MAX_ATTEMPTS - attempts
            await query.answer(get_text(lang, "captcha_wrong_attempt", attempts_left=attempts_left), show_alert=True)