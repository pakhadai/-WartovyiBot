import json
from fastapi import APIRouter, HTTPException, Body, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# Імпортуємо всі необхідні функції з інших модулів
from bot.infrastructure.localization import load_translation_file
from bot.infrastructure.database import (
    get_global_settings, set_global_setting,
    get_group_settings, set_group_setting,
    get_spam_triggers, add_spam_trigger, delete_spam_trigger,
    is_group_admin, get_user_chats
)
from bot.config import ADMIN_ID

router = APIRouter()

# --- Моделі для валідації даних, які приходять з Frontend ---
class SettingUpdate(BaseModel):
    key: str
    value: Any

class SpamTrigger(BaseModel):
    trigger: str = Field(..., min_length=2)
    score: int = Field(..., gt=0, lt=101)

class SpamTriggerDelete(BaseModel):
    trigger: str

class Chat(BaseModel):
    id: int
    name: str

# --- Функції для перевірки прав доступу ---
def get_user_id_from_header(user_data_raw: str) -> int:
    """Витягує user_id з хедеру X-User-Data."""
    if not user_data_raw:
        raise HTTPException(status_code=401, detail="Not authorized: Missing user data header")
    try:
        user_info = json.loads(user_data_raw)
        return user_info['id']
    except (json.JSONDecodeError, KeyError):
         raise HTTPException(status_code=400, detail="Invalid user data format")

async def verify_user_access(user_data_raw: str, chat_id: int) -> int:
    """Перевіряє, чи має користувач право керувати конкретним чатом."""
    user_id = get_user_id_from_header(user_data_raw)
    if not is_group_admin(user_id, chat_id):
        raise HTTPException(status_code=403, detail="Forbidden: You are not an admin of this chat")
    return user_id

async def verify_global_admin(user_data_raw: str) -> int:
    """Перевіряє, чи є користувач глобальним адміном бота."""
    user_id = get_user_id_from_header(user_data_raw)
    if user_id != ADMIN_ID:
        raise HTTPException(status_code=403, detail="Forbidden: Global settings can only be changed by the bot owner")
    return user_id

# --- API Роути ---

@router.get("/api/translations/{lang_code}")
async def get_translations(lang_code: str):
    """Віддає файл перекладу у форматі JSON."""
    try:
        return JSONResponse(content=load_translation_file(lang_code))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load translations: {e}")

@router.get("/api/my-chats", response_model=List[Chat])
async def get_my_chats(x_user_data: str = Header(None)):
    """Повертає список чатів, якими керує користувач."""
    user_id = get_user_id_from_header(x_user_data)
    return get_user_chats(user_id)

# --- Роути для Налаштувань ---

@router.get("/api/settings/global")
async def get_default_settings(x_user_data: str = Header(None)):
    """Отримує глобальні налаштування за замовчуванням."""
    await verify_global_admin(x_user_data)
    return get_global_settings()

@router.post("/api/settings/global")
async def update_default_setting(update: SettingUpdate, x_user_data: str = Header(None)):
    """Оновлює глобальне налаштування."""
    await verify_global_admin(x_user_data)
    allowed_keys = ["captcha_enabled", "spam_filter_enabled", "spam_threshold"]
    if update.key not in allowed_keys:
        raise HTTPException(status_code=400, detail="Invalid global setting key")
    set_global_setting(update.key, update.value)
    return {"status": "success"}

@router.get("/api/settings/{chat_id}")
async def get_chat_settings(chat_id: int, x_user_data: str = Header(None)):
    """Отримує налаштування для конкретної групи."""
    await verify_user_access(x_user_data, chat_id)
    return get_group_settings(chat_id)

@router.post("/api/settings/{chat_id}")
async def update_chat_setting(chat_id: int, update: SettingUpdate, x_user_data: str = Header(None)):
    """Оновлює налаштування для конкретної групи."""
    await verify_user_access(x_user_data, chat_id)
    allowed_keys = ["captcha_enabled", "spam_filter_enabled", "spam_threshold", "use_global_list", "use_custom_list"]
    if update.key not in allowed_keys:
        raise HTTPException(status_code=400, detail="Invalid group setting key")
    set_group_setting(chat_id, update.key, update.value)
    return {"status": "success"}

# --- Роути для Спам-слів (глобальні) ---

@router.get("/api/spam-words")
async def get_all_spam_words():
    """Повертає глобальний список спам-слів."""
    return get_spam_triggers()

@router.post("/api/spam-words")
async def add_new_spam_word(item: SpamTrigger, x_user_data: str = Header(None)):
    """Додає нове слово до глобального списку (тільки для адміна)."""
    await verify_global_admin(x_user_data)
    add_spam_trigger(item.trigger, item.score)
    return {"status": "success"}

@router.delete("/api/spam-words")
async def delete_existing_spam_word(item: SpamTriggerDelete = Body(...), x_user_data: str = Header(None)):
    """Видаляє слово з глобального списку (тільки для адміна)."""
    await verify_global_admin(x_user_data)
    delete_spam_trigger(item.trigger)
    return {"status": "success"}