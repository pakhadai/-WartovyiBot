import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def create_captcha_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Створює клавіатуру для капчі."""
    human_emojis = ['👨', '👩', '👶', '👴', '👵', '🧑', '👱', '👨‍🦰', '👩‍🦰']
    robot_emojis = ['🤖', '👾', '👽', '🛸', '🎮', '💾', '🖥️', '⚙️', '🔧']

    correct_emoji = random.choice(human_emojis)
    wrong_emojis = random.sample(robot_emojis, 3)

    options = [correct_emoji] + wrong_emojis
    random.shuffle(options)

    keyboard = [[
        InlineKeyboardButton(emoji, callback_data=f"captcha:{user_id}:{emoji}:{correct_emoji}")
        for emoji in options
    ]]
    return InlineKeyboardMarkup(keyboard)