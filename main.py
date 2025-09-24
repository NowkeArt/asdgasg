# main.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters
)
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
    handle_bug_action
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

def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user{user_id}"

    if user_id == SUPER_ADMIN_ID:
        add_admin(user_id, username)
        logger.info(f"✅ Суперадмин {username} (ID: {user_id}) добавлен при /start.")

    is_user_admin = is_admin(user_id)
    logger.info(f"🔍 Пользователь {username} (ID: {user_id}) — админ: {is_user_admin}")

    keyboard = [
        [InlineKeyboardButton("📄 Создать ТЗ", callback_data="create_task")],
        [InlineKeyboardButton("🐞 Сообщить о баге", callback_data="create_bug")],
    ]

    if not is_user_admin:
        keyboard.append([InlineKeyboardButton("📄 Подать заявку в команду", callback_data="apply_to_team")])

    if is_user_admin:
        keyboard.extend([
            [InlineKeyboardButton("📋 Активные ТЗ", callback_data="list_active")],
            [InlineKeyboardButton("✅ Выполненные ТЗ", callback_data="list_completed")],
            [InlineKeyboardButton("❌ Отклонённые ТЗ", callback_data="list_rejected")],
            [InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")],
        ])
        logger.info("✅ Меню админа сформировано.")
    else:
        logger.info("✅ Меню обычного пользователя сформировано.")

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "👋 Добро пожаловать в систему управления ТЗ и багами!\nВыберите действие:",
        reply_markup=reply_markup
    )

def get_user_id(update, context):
    user = update.effective_user
    update.message.reply_text(f"🔑 Ваш Telegram ID: `{user.id}`", parse_mode="Markdown")

def open_admin_panel_command(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("⛔ У вас нет доступа к админ-панель.")
        return
    admin_panel(update, context)

def cancel_any_process(update, context):
    user_id = update.effective_user.id

    # Импортируем состояния
    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA
    from application_system import USER_APPLICATION

    if user_id in TASK_USER_DATA:
        del TASK_USER_DATA[user_id]
        update.message.reply_text("🚫 Создание ТЗ отменено.")
    elif user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]
        update.message.reply_text("🚫 Создание бага отменено.")
    elif user_id in USER_APPLICATION:
        del USER_APPLICATION[user_id]
        update.message.reply_text("🚫 Подача заявки отменена.")
    else:
        update.message.reply_text("ℹ️ Нет активного процесса.")

def button_handler(update, context):
    query = update.callback_query
    query.answer()
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
        handlers_map[data](update, context)
    elif data.startswith("bug_complete_") or data.startswith("bug_progress_") or data.startswith("bug_reject_"):
        handle_bug_action(update, context)
    elif data.startswith("complete_") or data.startswith("reject_"):
        handle_admin_action(update, context)
    elif data.startswith("app_approve_") or data.startswith("app_reject_"):
        handle_application_action(update, context)

def handle_text_input(update, context):
    user_id = update.effective_user.id

    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA
    from application_system import USER_APPLICATION, QUESTIONS

    if user_id in USER_APPLICATION:
        current_step = USER_APPLICATION.get(user_id, {}).get('step')
        if isinstance(current_step, int) and 0 <= current_step < len(QUESTIONS):
            handle_application_answer(update, context)
        return

    if user_id in TASK_USER_DATA:
        current_step = TASK_USER_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_description':
            handle_description(update, context)
        elif current_step == 'awaiting_media':
            update.message.reply_text("📸 Пожалуйста, прикрепите фото/видео или отправьте /skip")
        return

    if user_id in USER_BUG_DATA:
        current_step = USER_BUG_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_description':
            handle_bug_description(update, context)
        elif current_step == 'awaiting_media':
            update.message.reply_text("📸 Пожалуйста, прикрепите скриншот/видео или отправьте /skip_bug")
        return

    update.message.reply_text("ℹ️ Начните с команды /start")

def handle_media_input(update, context):
    user_id = update.effective_user.id

    from task_system import USER_DATA as TASK_USER_DATA
    from bug_system import USER_BUG_DATA

    if user_id in TASK_USER_DATA:
        current_step = TASK_USER_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_media':
            handle_media_or_skip(update, context)
        return

    if user_id in USER_BUG_DATA:
        current_step = USER_BUG_DATA.get(user_id, {}).get('step')
        if current_step == 'awaiting_media':
            handle_bug_media_or_skip(update, context)
        return

def main():
    # Инициализация БД
    init_db()
    add_admin(SUPER_ADMIN_ID, "superadmin")
    logger.info(f"✅ Суперадмин (ID: {SUPER_ADMIN_ID}) добавлен при запуске.")

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("skip", skip_media))
    dp.add_handler(CommandHandler("skip_bug", skip_bug_media))
    dp.add_handler(CommandHandler("cancel", cancel_any_process))
    dp.add_handler(CommandHandler("admin", open_admin_panel_command))
    dp.add_handler(CommandHandler("id", get_user_id))

    # Обработчики
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.chat_type.private,
        handle_text_input
    ))
    dp.add_handler(MessageHandler(
        (Filters.photo | Filters.video) & Filters.chat_type.private,
        handle_media_input
    ))
    dp.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ Бот запущен и готов к работе.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()