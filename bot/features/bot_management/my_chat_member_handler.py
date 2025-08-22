# pakhadai/wartovyi/Wartovyi-7768a1de9d0807b9ea35ec577aa9030b711895bc/bot/features/bot_management/my_chat_member_handler.py

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

# Імпортуємо нову та існуючі функції з бази даних
from bot.infrastructure.database import add_group_if_not_exists, set_group_admin, delete_all_group_data


async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    chat = my_chat_member.chat
    user = my_chat_member.from_user

    old_status = my_chat_member.old_chat_member.status
    new_status = my_chat_member.new_chat_member.status

    # Випадок 1: Бота додали в новий чат як адміністратора
    if new_status == ChatMemberStatus.ADMINISTRATOR and old_status != ChatMemberStatus.ADMINISTRATOR:
        logging.info(f"Бот був доданий в чат '{chat.title}' ({chat.id}) користувачем {user.full_name} ({user.id})")

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

    # Випадок 2: Бота видалили з чату або забанили
    elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        logging.info(f"Бота видалили з чату '{chat.title}' ({chat.id}). Видаляю всі пов'язані дані.")
        delete_all_group_data(chat.id)