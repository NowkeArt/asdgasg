# main.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, SUPER_ADMIN_ID
from database import init_db, add_admin, is_admin

# Импортируем все обработчики из модулей
from task_system import (
    create_task_start, confirm_task, edit_task, cancel_task,
    list_active, list_completed, list_rejected,
    handle_description, handle_media_or_skip, skip_media,
    handle_admin_action
)
from bug_system import (
    create_bug_start, confirm_bug, edit_bug, cancel_bug,
    handle_bug_description, handle_bug_media_or_skip, skip_bug_media,
    handle_bug_action, list_bugs_active, list_bugs_in_progress,
    list_bugs_completed, list_bugs_rejected
)
from admin_panel import (
    admin_panel, add_admin_start, handle_admin_username,
    list_admins, back_to_main
)
from application_system import (
    start_application, set_position, handle_application_answer,
    confirm_application, edit_application, cancel_application,
    handle_application_action
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная клавиатура главного меню
MAIN_MENU_KEYBOARD = [
    [InlineKeyboardButton("📄 Создать ТЗ", callback_data="create_task")],
    [InlineKeyboardButton("🐞 Сообщить о баге", callback_data="create_bug")],
    [InlineKeyboardButton("📋 Мои баги", callback_data="my_bugs_menu")],
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user{user_id}"

    # Добавляем суперадмина при первом запуске
    if user_id == SUPER_ADMIN_ID:
        await add_admin(user_id, f"@{username}")
        logger.info(f"✅ Суперадмин {username} (ID: {user_id}) добавлен при /start.")

    is_user_admin = await is_admin(user_id)
    logger.info(f"🔍 Пользователь {username} (ID: {user_id}) — админ: {is_user_admin}")

    keyboard = MAIN_MENU_KEYBOARD.copy()

    # Добавляем кнопку подачи заявки для обычных пользователей
    if not is_user_admin:
        keyboard.append([InlineKeyboardButton("📄 Подать заявку в команду", callback_data="apply_to_team")])

    # Добавляем админские кнопки
    if is_user_admin:
        keyboard.extend([
            [InlineKeyboardButton("📋 Активные ТЗ", callback_data="list_active")],
            [InlineKeyboardButton("✅ Выполненные ТЗ", callback_data="list_completed")],
            [InlineKeyboardButton("❌ Отклонённые ТЗ", callback_data="list_rejected")],
            [InlineKeyboardButton("🐛 Админ баги", callback_data="admin_bugs_menu")],
        ])
        
        # Только суперадмин видит админ-панель
        if user_id == SUPER_ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
        
        logger.info("✅ Меню админа сформировано.")
    else:
        logger.info("✅ Меню обычного пользователя сформировано.")

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать в систему управления ТЗ и багами!\nВыберите действие:",
        reply_markup=reply_markup
    )

async def my_bugs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⏳ В ожидании", callback_data="list_bugs_active")],
        [InlineKeyboardButton("🛠️ В работе", callback_data="list_bugs_in_progress")],
        [InlineKeyboardButton("✅ Исправленные", callback_data="list_bugs_completed")],
        [InlineKeyboardButton("❌ Отклонённые", callback_data="list_bugs_rejected")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🐞 Мои баги:", reply_markup=reply_markup)

async def admin_bugs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await query.message.reply_text("⛔ У вас нет прав администратора.")
        return
    
    keyboard = [
        [InlineKeyboardButton("⏳ Все в ожидании", callback_data="list_bugs_active")],
        [InlineKeyboardButton("🛠️ Все в работе", callback_data="list_bugs_in_progress")],
        [InlineKeyboardButton("✅ Все исправленные", callback_data="list_bugs_completed")],
        [InlineKeyboardButton("❌ Все отклонённые", callback_data="list_bugs_rejected")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🐛 Все баги (админ):", reply_markup=reply_markup)

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"🔑 Ваш Telegram ID: `{user.id}`", parse_mode="Markdown")

async def open_admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != SUPER_ADMIN_ID:
        await update.message.reply_text("⛔ Только суперадмин может управлять админами.")
        return
    await admin_panel(update, context)

async def cancel_any_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Импортируем состояния
    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA
    from application_system import USER_APPLICATION
    from admin_panel import USER_DATA as ADMIN_USER_DATA

    if user_id in TASK_USER_DATA:
        del TASK_USER_DATA[user_id]
        await update.message.reply_text("🚫 Создание ТЗ отменено.")
    elif user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]
        await update.message.reply_text("🚫 Создание бага отменено.")
    elif user_id in USER_APPLICATION:
        del USER_APPLICATION[user_id]
        await update.message.reply_text("🚫 Подача заявки отменена.")
    elif user_id in ADMIN_USER_DATA:
        del ADMIN_USER_DATA[user_id]
        await update.message.reply_text("🚫 Процесс отменён.")
    else:
        await update.message.reply_text("ℹ️ Нет активного процесса.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    handlers_map = {
        "create_task": create_task_start,
        "confirm_task": confirm_task,
        "edit_task": edit_task,
        "cancel_task": cancel_task,
        "list_active": list_active,
        "list_completed": list_completed,
        "list_rejected": list_rejected,
        "create_bug": create_bug_start,
        "confirm_bug": confirm_bug,
        "edit_bug": edit_bug,
        "cancel_bug": cancel_bug,
        "my_bugs_menu": my_bugs_menu,
        "admin_bugs_menu": admin_bugs_menu,
        "list_bugs_active": list_bugs_active,
        "list_bugs_in_progress": list_bugs_in_progress,
        "list_bugs_completed": list_bugs_completed,
        "list_bugs_rejected": list_bugs_rejected,
        "apply_to_team": start_application,
        "apply_helper": set_position,
        "apply_moderator": set_position,
        "confirm_application": confirm_application,
        "edit_application": edit_application,
        "cancel_application": cancel_application,
        "admin_panel": admin_panel,
        "add_admin_start": add_admin_start,
        "list_admins": list_admins,
        "back_to_main": back_to_main,
    }

    if data in handlers_map:
        await handlers_map[data](update, context)
    elif data.startswith("bug_complete_") or data.startswith("bug_progress_") or data.startswith("bug_reject_"):
        await handle_bug_action(update, context)
    elif data.startswith("complete_") or data.startswith("reject_"):
        await handle_admin_action(update, context)
    elif data.startswith("app_approve_") or data.startswith("app_reject_"):
        await handle_application_action(update, context)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA
    from application_system import USER_APPLICATION, QUESTIONS
    from admin_panel import USER_DATA as ADMIN_USER_DATA

    # Обработка заявок
    if user_id in USER_APPLICATION:
        current_step = USER_APPLICATION.get(user_id, {}).get('step')
        if isinstance(current_step, int) and 0 <= current_step < len(QUESTIONS):
            await handle_application_answer(update, context)
        return

    # Обработка админ-панели
    if user_id in ADMIN_USER_DATA:
        current_step = ADMIN_USER_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_admin_username':
            await handle_admin_username(update, context)
        return

    # Обработка ТЗ
    if user_id in TASK_USER_DATA:
        current_step = TASK_USER_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_description':
            await handle_description(update, context)
        elif current_step == 'awaiting_media':
            await update.message.reply_text("📸 Пожалуйста, прикрепите фото/видео или отправьте /skip")
        return

    # Обработка багов
    if user_id in USER_BUG_DATA:
        current_step = USER_BUG_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_description':
            await handle_bug_description(update, context)
        elif current_step == 'awaiting_media':
            await update.message.reply_text("📸 Пожалуйста, прикрепите скриншот/видео или отправьте /skip_bug")
        return

    await update.message.reply_text("ℹ️ Начните с команды /start")

async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA

    if user_id in TASK_USER_DATA:
        current_step = TASK_USER_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_media':
            await handle_media_or_skip(update, context)
        return

    if user_id in USER_BUG_DATA:
        current_step = USER_BUG_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_media':
            await handle_bug_media_or_skip(update, context)
        return

async def main():
    # Инициализация БД
    await init_db()

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("skip", skip_media))
    application.add_handler(CommandHandler("skip_bug", skip_bug_media))
    application.add_handler(CommandHandler("cancel", cancel_any_process))
    application.add_handler(CommandHandler("admin", open_admin_panel_command))
    application.add_handler(CommandHandler("id", get_user_id))

    # Обработчики
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_text_input
    ))
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO) & filters.ChatType.PRIVATE,
        handle_media_input
    ))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ Бот запущен и готов к работе.")
    
    # Запускаем бота с обработкой ошибок
    try:
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":