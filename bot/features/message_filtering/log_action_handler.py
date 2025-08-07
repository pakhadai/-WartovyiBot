import logging
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config import ADMIN_ID
from bot.infrastructure.localization import get_text

async def log_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin = query.from_user
    lang = admin.language_code

    if admin.id != ADMIN_ID:
        await query.answer(get_text(lang, "not_admin"), show_alert=True)
        return

    await query.answer()
    try:
        _, action, user_id_str, chat_id_str = query.data.split(":", 3)
        user_id, chat_id = int(user_id_str), int(chat_id_str)
    except (ValueError, IndexError) as e:
        logging.error(f"Invalid callback data format: {query.data} ({e})")
        return

    action_text = ""
    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            action_text = "забанено"
        elif action == "unrestrict":
            await context.bot.restrict_chat_member(
                chat_id=chat_id, user_id=user_id,
                permissions=ChatPermissions(can_send_messages=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True)
            )
            action_text = "розблоковано"
        elif action == "ignore":
            action_text = "проігноровано"

        original_text = query.message.text_html
        new_text = original_text + get_text(lang, "log_action_by", action_text=action_text)
        await query.edit_message_text(new_text, reply_markup=None, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Error processing log action '{action}': {e}")