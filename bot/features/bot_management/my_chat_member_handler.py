import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

from bot.infrastructure.database import add_group_if_not_exists, set_group_admin


async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    my_chat_member = update.my_chat_member

    if not my_chat_member:
        return

    chat = my_chat_member.chat
    user = my_chat_member.from_user
    new_status = my_chat_member.new_chat_member.status

    # Бот був доданий в новий чат як адміністратор
    if new_status == ChatMemberStatus.ADMINISTRATOR:
        logging.info(f"Бот був доданий в чат '{chat.title}' ({chat.id}) користувачем {user.full_name} ({user.id})")
        add_group_if_not_exists(chat.id, chat.title)
        logging.info(f"[DEBUG] Ensured group {chat.id} exists in DB.")
        set_group_admin(chat.id, user.id)
        logging.info(f"[DEBUG] Set user {user.id} as admin for group {chat.id}.")
        # Додаємо групу в БД, якщо її там немає
        add_group_if_not_exists(chat.id, chat.title)

        # Призначаємо користувача, що додав бота, як "Власника групи"
        set_group_admin(chat.id, user.id)

        try:
            # Намагаємось надіслати привітальне повідомлення власнику
            await context.bot.send_message(
                chat_id=user.id,
                text=f"Привіт! Ви додали мене в чат «{chat.title}».\n\n"
                     f"Тепер ви можете керувати його налаштуваннями через мою панель. "
                     f"Відкрийте приватний чат зі мною та натисніть кнопку 'Меню' внизу."
            )
        except Exception as e:
            logging.warning(f"Не вдалося надіслати повідомлення користувачу {user.id}: {e}")

    # TODO: Тут можна додати логіку, коли бота видаляють з чату або забирають права