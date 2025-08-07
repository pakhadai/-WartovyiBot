from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import ADMIN_ID, WEB_APP_URL
from bot.infrastructure.localization import get_text


async def launch_settings_web_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = user.language_code

    if user.id != ADMIN_ID:
        await update.message.reply_text(get_text(lang, "not_admin"))
        return

    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, "settings_button"),
            web_app={"url": WEB_APP_URL}
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        get_text(lang, "settings_open"),
        reply_markup=reply_markup
    )