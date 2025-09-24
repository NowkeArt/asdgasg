# admin_panel.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *  # ✅ Исправлено
from config import SUPER_ADMIN_ID

USER_DATA = {}

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != SUPER_ADMIN_ID:
        await query.message.reply_text("⛔ Только суперадмин может управлять админами.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin_start")],
        [InlineKeyboardButton("📋 Список админов", callback_data="list_admins")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("👑 Админ-панель:", reply_markup=reply_markup)

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != SUPER_ADMIN_ID:
        return
    USER_DATA[user_id] = {'step': 'awaiting_admin_username'}
    await query.message.reply_text("✏️ Отправьте @username пользователя для назначения админом:")

async def handle_admin_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_DATA.get(user_id, {}).get('step') == 'awaiting_admin_username':
        username = update.message.text.strip()
        if not username.startswith("@"):
            await update.message.reply_text("❌ Имя пользователя должно начинаться с @")
            return

        await add_admin(0, username)
        await update.message.reply_text(f"✅ Админ {username} добавлен (user_id=0, требуется ручная настройка).")
        del USER_DATA[user_id]

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admins = await get_admins()  # ✅ Теперь работает
    if not admins:
        text = "📭 Нет администраторов."
    else:
        text = "📋 Список администраторов:\n" + "\n".join([f"• {username} (ID: {uid})" for uid, username in admins])
    await query.message.reply_text(text)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from main import MAIN_MENU_KEYBOARD
    keyboard = MAIN_MENU_KEYBOARD.copy()
    user_id = update.effective_user.id
    if await is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("⬅️ Главное меню:", reply_markup=reply_markup)