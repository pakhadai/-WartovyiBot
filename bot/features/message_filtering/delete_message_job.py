from telegram.ext import ContextTypes

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Видаляє повідомлення через певний час."""
    try:
        await context.bot.delete_message(
            chat_id=context.job.data['chat_id'],
            message_id=context.job.data['message_id']
        )
    except Exception:
        pass