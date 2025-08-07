from telegram import Update
from telegram.ext import ContextTypes
from bot.infrastructure.localization import get_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code
    await update.message.reply_text(get_text(lang, "start"))