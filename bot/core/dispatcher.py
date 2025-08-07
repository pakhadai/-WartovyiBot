from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, filters
from telegram.constants import ChatMemberStatus

# Імпортуємо всі наші обробники
from bot.features.common_commands.start_handler import start
from bot.features.admin_panel_web.launch_handler import launch_settings_web_app
from bot.features.group_join.new_member_handler import new_member_handler
from bot.features.group_join.captcha_handler import captcha_handler
from bot.features.message_filtering.message_handler import message_handler
from bot.features.message_filtering.log_action_handler import log_action_handler
from bot.features.bot_management.my_chat_member_handler import my_chat_member_handler

def register_handlers(app: Application):
    """Реєструє всі обробники в додатку."""

    # 1. Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", launch_settings_web_app))

    # 2. Обробники подій у групі (вхід, капча, логи)
    app.add_handler(ChatMemberHandler(new_member_handler, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(captcha_handler, pattern=r"^captcha:"))
    app.add_handler(CallbackQueryHandler(log_action_handler, pattern=r"^log:"))

    # 3. Обробник повідомлень (має бути одним з останніх)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, message_handler))
    app.add_handler(ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER))
