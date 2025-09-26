# main.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, SUPER_ADMIN_ID, GROUP_CHAT_ID, TOPIC_THREAD_ID_BUGS, TOPIC_THREAD_ID_APPS
from database import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для FSM
USER_DATA = {}
USER_BUG_DATA = {}
USER_APPLICATION = {}
ADMIN_USER_DATA = {}

# Вопросы для заявок
QUESTIONS = [
    "1. Ваш часовой пояс?",
    "2. Есть ли опыт модерации? Если да, то укажите проект и длительность поста.",
    "3. Состоите ли Вы на данный момент в администрации/модерации/команде на ином проекте?",
    "4. Знаете ли Вы, как проводить проверку на читы?",
    "5. Общий Опыт/Длительность игры на серверах типу Анка/Гриф?",
    "6. Ваш возраст?",
    "7. Время, которое вы готовы выделять на сервер в день (можно указать промежуток времени и дни)."
]

# Главное меню
def get_main_menu_keyboard(is_admin: bool, is_super_admin: bool):
    keyboard = [
        [InlineKeyboardButton("📄 Создать ТЗ", callback_data="create_task")],
        [InlineKeyboardButton("🐞 Сообщить о баге", callback_data="create_bug")],
        [InlineKeyboardButton("📋 Мои баги", callback_data="my_bugs_menu")],
    ]
    
    if not is_admin:
        keyboard.append([InlineKeyboardButton("📄 Подать заявку в команду", callback_data="apply_to_team")])
    
    if is_admin:
        keyboard.extend([
            [InlineKeyboardButton("📋 Активные ТЗ", callback_data="list_active")],
            [InlineKeyboardButton("✅ Выполненные ТЗ", callback_data="list_completed")],
            [InlineKeyboardButton("❌ Отклонённые ТЗ", callback_data="list_rejected")],
            [InlineKeyboardButton("🐛 Админ баги", callback_data="admin_bugs_menu")],
        ])
        
        if is_super_admin:
            keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    return keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user{user_id}"

    # Добавляем суперадмина при первом запуске
    if user_id == SUPER_ADMIN_ID:
        await add_admin(user_id, f"@{username}")
        logger.info(f"✅ Суперадмин {username} (ID: {user_id}) добавлен при /start.")

    is_user_admin = await is_admin(user_id)
    is_super_admin = user_id == SUPER_ADMIN_ID
    
    keyboard = get_main_menu_keyboard(is_user_admin, is_super_admin)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Добро пожаловать в систему управления ТЗ и багами!\nВыберите действие:",
        reply_markup=reply_markup
    )

# === СИСТЕМА ТЗ ===

async def create_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("📝 Введите описание задачи:")

async def handle_task_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_DATA[user_id]['description'] = update.message.text
    USER_DATA[user_id]['step'] = 'awaiting_media'
    await update.message.reply_text("📸 Прикрепите фото/видео (опционально) или отправьте /skip")

async def handle_task_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        USER_DATA[user_id]['media_file_id'] = file_id
    elif update.message.video:
        file_id = update.message.video.file_id
        USER_DATA[user_id]['media_file_id'] = file_id
    else:
        USER_DATA[user_id]['media_file_id'] = None

    await show_task_preview(update, context)

async def skip_task_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_DATA:
        USER_DATA[user_id]['media_file_id'] = None
        await show_task_preview(update, context)

async def show_task_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = USER_DATA[user_id]
    
    desc = data['description']
    media = data.get('media_file_id')

    text = f"🔍 Предпросмотр ТЗ:\n\n{desc}"
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_task")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="edit_task")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_task")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if media:
        if update.message and update.message.photo:
            await update.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
        elif update.message and update.message.video:
            await update.message.reply_video(video=media, caption=text, reply_markup=reply_markup)
        else:
            await context.bot.send_photo(chat_id=user_id, photo=media, caption=text, reply_markup=reply_markup)
    else:
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

    USER_DATA[user_id]['step'] = 'preview'

async def confirm_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = USER_DATA.get(user_id)

    if not data or data.get('step') != 'preview':
        await query.message.reply_text("❌ Сессия устарела. Начните заново с /start")
        return

    author_username = update.effective_user.username or "user"
    task_id = await create_task(
        author_id=user_id,
        author_username=f"@{author_username}",
        description=data['description'],
        media_file_id=data.get('media_file_id')
    )

    # Отправляем всем админам
    admins = await get_admins()
    sent_to_anyone = False

    for admin_id, username in admins:
        try:
            text = f"📄 Новое ТЗ #{task_id} от @{author_username}:\n\n{data['description']}"
            keyboard = [
                [
                    InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if data.get('media_file_id'):
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=data['media_file_id'],
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=reply_markup
                )
            sent_to_anyone = True
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {username}: {e}")

    if sent_to_anyone:
        await query.message.reply_text("✅ ТЗ успешно создано и отправлено администраторам!")
    else:
        await query.message.reply_text("⚠️ Не удалось отправить ТЗ администраторам.")

    del USER_DATA[user_id]

async def edit_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("✏️ Введите новое описание задачи:")

async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_DATA:
        del USER_DATA[user_id]
    await query.message.reply_text("🚫 Создание ТЗ отменено.")

async def handle_admin_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if not await is_admin(user_id):
        await query.message.reply_text("⛔ У вас нет прав администратора.")
        return

    data = query.data
    if data.startswith("complete_"):
        task_id = int(data.split("_")[1])
        status = "completed"
        action_text = "✅ выполнено"
    elif data.startswith("reject_"):
        task_id = int(data.split("_")[1])
        status = "rejected"
        action_text = "❌ отклонено"
    else:
        return

    admin_username = update.effective_user.username or "admin"
    await update_task_status(task_id, status, user_id, f"@{admin_username}")

    # Уведомляем автора
    task = await get_task_by_id(task_id)
    if task:
        author_id = task[1]
        desc = task[3]
        try:
            await context.bot.send_message(
                chat_id=author_id,
                text=f"🔔 Ваше ТЗ:\n\n{desc}\n\nбыло {action_text} администратором @{admin_username}."
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить автора {author_id}: {e}")

    await query.message.edit_text(
        text=query.message.text + f"\n\n📌 Статус: {action_text.upper()}",
        reply_markup=None
    )

# === СИСТЕМА БАГОВ ===

async def create_bug_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_BUG_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("🐞 Опишите баг (что сломалось, как воспроизвести):")

async def handle_bug_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_BUG_DATA[user_id]['description'] = update.message.text
    USER_BUG_DATA[user_id]['step'] = 'awaiting_media'
    await update.message.reply_text("📸 Прикрепите скриншот/видео (опционально) или отправьте /skip_bug")

async def handle_bug_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        USER_BUG_DATA[user_id]['media_file_id'] = file_id
    elif update.message.video:
        file_id = update.message.video.file_id
        USER_BUG_DATA[user_id]['media_file_id'] = file_id
    else:
        USER_BUG_DATA[user_id]['media_file_id'] = None

    await show_bug_preview(update, context)

async def skip_bug_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_BUG_DATA:
        USER_BUG_DATA[user_id]['media_file_id'] = None
        await show_bug_preview(update, context)

async def show_bug_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = USER_BUG_DATA[user_id]
    
    desc = data['description']
    media = data.get('media_file_id')

    text = f"🔍 Предпросмотр бага:\n\n{desc}"
    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="confirm_bug")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="edit_bug")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_bug")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if media:
        if update.message and update.message.photo:
            await update.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
        elif update.message and update.message.video:
            await update.message.reply_video(video=media, caption=text, reply_markup=reply_markup)
        else:
            await context.bot.send_photo(chat_id=user_id, photo=media, caption=text, reply_markup=reply_markup)
    else:
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

    USER_BUG_DATA[user_id]['step'] = 'preview'

async def confirm_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = USER_BUG_DATA.get(user_id)

    if not data or data.get('step') != 'preview':
        await query.message.reply_text("❌ Сессия устарела. Начните заново с /start")
        return

    author_username = update.effective_user.username or "user"
    
    try:
        bug_id = await create_bug(
            author_id=user_id,
            author_username=f"@{author_username}",
            description=data['description'],
            media_file_id=data.get('media_file_id')
        )
        
        # Отправляем в группу
        text = f"🐞 Баг #{bug_id} от @{author_username}:\n\n{data['description']}\n\nСтатус: ⏳ Ожидает обработки"
        
        keyboard = [
            [
                InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
                InlineKeyboardButton("🟡 Выполняется", callback_data=f"bug_progress_{bug_id}"),
                InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if data.get('media_file_id'):
            sent_message = await context.bot.send_photo(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=TOPIC_THREAD_ID_BUGS,
                photo=data['media_file_id'],
                caption=text,
                reply_markup=reply_markup
            )
        else:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=TOPIC_THREAD_ID_BUGS,
                text=text,
                reply_markup=reply_markup
            )

        await update_bug_status(bug_id, "pending", 0, "system", sent_message.message_id)
        await query.message.reply_text("✅ Баг отправлен в группу на рассмотрение!")
        
    except Exception as e:
        logger.error(f"Ошибка создания бага: {e}")
        await query.message.reply_text("❌ Не удалось создать баг. Попробуйте позже.")

    if user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]

async def edit_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_BUG_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("✏️ Введите новое описание бага:")

async def cancel_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]
    await query.message.reply_text("🚫 Создание бага отменено.")

async def handle_bug_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await query.message.reply_text("⛔ Только администраторы могут менять статус багов.")
        return

    data = query.data
    bug_id = None
    status = ""
    emoji = ""

    if data.startswith("bug_complete_"):
        bug_id = int(data.split("_")[2])
        status = "completed"
        emoji = "✅"
    elif data.startswith("bug_progress_"):
        bug_id = int(data.split("_")[2])
        status = "in_progress"
        emoji = "🛠️"
    elif data.startswith("bug_reject_"):
        bug_id = int(data.split("_")[2])
        status = "rejected"
        emoji = "❌"
    else:
        return

    admin_username = update.effective_user.username or "admin"
    bug = await get_bug_by_id(bug_id)
    if not bug:
        await query.message.reply_text("❌ Баг не найден.")
        return

    await update_bug_status(bug_id, status, user_id, f"@{admin_username}")

    # Уведомляем автора
    author_id = bug[1]
    desc = bug[3]
    try:
        await context.bot.send_message(
            chat_id=author_id,
            text=f"🔔 Ваш баг:\n\n{desc}\n\nизменил статус на: {emoji} {status} (администратор @{admin_username})"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить автора бага {author_id}: {e}")

    # Обновляем сообщение в группе
    message_id_in_group = bug[7]
    if message_id_in_group:
        try:
            new_text = query.message.text.split("\n\nСтатус:")[0] + f"\n\nСтатус: {emoji} {status}"
            
            # Генерируем новую клавиатуру
            keyboard = []
            if status == "in_progress":
                keyboard = [
                    [
                        InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
                        InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
                    ]
                ]
            elif status not in ["completed", "rejected"]:
                keyboard = [
                    [
                        InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
                        InlineKeyboardButton("🟡 Выполняется", callback_data=f"bug_progress_{bug_id}"),
                        InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
                    ]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=message_id_in_group,
                text=new_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение бага в группе: {e}")

    # Обновляем сообщение у админа
    await query.message.edit_text(
        text=query.message.text.split("\n\nСтатус:")[0] + f"\n\nСтатус: {emoji} {status}",
        reply_markup=None
    )

# === МЕНЮ И СПИСКИ ===

async def my_bugs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⏳ В ожидании", callback_data="list_bugs_pending")],
        [InlineKeyboardButton("🛠️ В работе", callback_data="list_bugs_progress")],
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
        [InlineKeyboardButton("⏳ Все в ожидании", callback_data="list_bugs_pending_all")],
        [InlineKeyboardButton("🛠️ Все в работе", callback_data="list_bugs_progress_all")],
        [InlineKeyboardButton("✅ Все исправленные", callback_data="list_bugs_completed_all")],
        [InlineKeyboardButton("❌ Все отклонённые", callback_data="list_bugs_rejected_all")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🐛 Все баги (админ):", reply_markup=reply_markup)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    is_user_admin = await is_admin(user_id)
    is_super_admin = user_id == SUPER_ADMIN_ID
    
    keyboard = get_main_menu_keyboard(is_user_admin, is_super_admin)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("⬅️ Главное меню:", reply_markup=reply_markup)

# === ОБРАБОТЧИКИ СООБЩЕНИЙ ===

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Обработка ТЗ
    if user_id in USER_DATA:
        step = USER_DATA[user_id].get('step')
        if step == 'awaiting_description':
            await handle_task_description(update, context)
            return
    
    # Обработка багов
    if user_id in USER_BUG_DATA:
        step = USER_BUG_DATA[user_id].get('step')
        if step == 'awaiting_description':
            await handle_bug_description(update, context)
            return
    
    # Обработка заявок
    if user_id in USER_APPLICATION:
        step = USER_APPLICATION[user_id].get('step')
        if isinstance(step, int) and 0 <= step < len(QUESTIONS):
            await handle_application_answer(update, context)
            return
    
    # Обработка админ-панели
    if user_id in ADMIN_USER_DATA:
        step = ADMIN_USER_DATA[user_id].get('step')
        if step == 'awaiting_admin_username':
            await handle_admin_username(update, context)
            return
    
    await update.message.reply_text("ℹ️ Начните с команды /start")

async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Обработка медиа для ТЗ
    if user_id in USER_DATA:
        step = USER_DATA[user_id].get('step')
        if step == 'awaiting_media':
            await handle_task_media(update, context)
            return
    
    # Обработка медиа для багов
    if user_id in USER_BUG_DATA:
        step = USER_BUG_DATA[user_id].get('step')
        if step == 'awaiting_media':
            await handle_bug_media(update, context)
            return
    
    await update.message.reply_text("📸 Медиафайл получен, но нет активного процесса.")

# === СИСТЕМА ЗАЯВОК ===

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    
    # Проверка на повторную заявку
    app = await get_last_application(user_id)
    if app:
        from datetime import datetime, timedelta
        created_at = datetime.strptime(app[13], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - created_at < timedelta(days=7):
            await query.message.reply_text(
                "⏳ Вы уже подавали заявку в течение последних 7 дней. Повторно можно через 7 дней с момента подачи."
            )
            return

    keyboard = [
        [InlineKeyboardButton("🛠️ Хелпер", callback_data="apply_helper")],
        [InlineKeyboardButton("🛡️ Модератор", callback_data="apply_moderator")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_application")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "Выберите должность, на которую хотите подать заявку:",
        reply_markup=reply_markup
    )

async def set_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "apply_helper":
        position = "Хелпер"
    elif data == "apply_moderator":
        position = "Модератор"
    else:
        return

    USER_APPLICATION[user_id] = {
        'step': 0,
        'position': position,
        'answers': []
    }
    await query.message.reply_text(f"Вы выбрали: {position}\n\n{QUESTIONS[0]}")

async def handle_application_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in USER_APPLICATION:
        return

    app_data = USER_APPLICATION[user_id]
    if app_data['step'] >= len(QUESTIONS):
        return

    app_data['answers'].append(update.message.text)
    app_data['step'] += 1

    if app_data['step'] < len(QUESTIONS):
        await update.message.reply_text(QUESTIONS[app_data['step']])
    else:
        text = f"📄 Заявка на должность: {app_data['position']}\n\n"
        for i, q in enumerate(QUESTIONS):
            text += f"{q}\nОтвет: {app_data['answers'][i]}\n\n"

        keyboard = [
            [InlineKeyboardButton("✅ Отправить", callback_data="confirm_application")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="edit_application")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_application")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        app_data['step'] = 'preview'

async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    app_data = USER_APPLICATION.get(user_id)

    if not app_data or app_data.get('step') != 'preview':
        await query.message.reply_text("❌ Сессия устарела. Начните заново.")
        return

    username = update.effective_user.username or f"user{user_id}"
    
    try:
        app_id = await create_application(user_id, f"@{username}", app_data['position'], app_data['answers'])
        
        # Отправка в группу
        text = f"📄 Заявка #{app_id} на должность: {app_data['position']}\nОт: @{username}\n\n"
        for i, q in enumerate(QUESTIONS):
            text += f"{q}\nОтвет: {app_data['answers'][i]}\n\n"

        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"app_approve_{app_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"app_reject_{app_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent_message = await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            message_thread_id=TOPIC_THREAD_ID_APPS,
            text=text,
            reply_markup=reply_markup
        )
        
        await update_application_message_id(app_id, sent_message.message_id)
        await query.message.reply_text("✅ Ваша заявка отправлена! Ожидайте решения.")
        
    except Exception as e:
        logger.error(f"Ошибка отправки заявки: {e}")
        await query.message.reply_text("❌ Не удалось отправить заявку. Попробуйте позже.")

    if user_id in USER_APPLICATION:
        del USER_APPLICATION[user_id]

async def edit_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_APPLICATION:
        USER_APPLICATION[user_id] = {
            'step': 0,
            'position': USER_APPLICATION[user_id]['position'],
            'answers': []
        }
        await query.message.reply_text(QUESTIONS[0])

async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_APPLICATION:
        del USER_APPLICATION[user_id]
    await query.message.reply_text("🚫 Подача заявки отменена.")

async def handle_application_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await query.message.reply_text("⛔ Только администраторы могут принимать заявки.")
        return

    data = query.data
    app_id = None
    status = ""
    message = ""

    if data.startswith("app_approve_"):
        app_id = int(data.split("_")[2])
        status = "approved"
        message = "✅ Ваша заявка одобрена! Ожидайте, когда вам напишет модератор."
    elif data.startswith("app_reject_"):
        app_id = int(data.split("_")[2])
        status = "rejected"
        message = "❌ Ваша заявка отклонена."
    else:
        return

    app = await get_application_by_id(app_id)
    if not app:
        await query.message.reply_text("❌ Заявка не найдена.")
        return

    await update_application_status(app_id, status)

    # Уведомляем автора
    author_id = app[1]
    try:
        await context.bot.send_message(chat_id=author_id, text=message)
    except Exception as e:
        logger.error(f"Не удалось уведомить автора заявки {author_id}: {e}")

    # Обновляем сообщение в группе
    await query.message.edit_text(
        text=query.message.text + f"\n\n📌 Статус: {'ОДОБРЕНО' if status == 'approved' else 'ОТКЛОНЕНО'}",
        reply_markup=None
    )

# === АДМИН-ПАНЕЛЬ ===

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
        
    ADMIN_USER_DATA[user_id] = {'step': 'awaiting_admin_username'}
    await query.message.reply_text("✏️ Отправьте @username пользователя для назначения админом:")

async def handle_admin_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_USER_DATA.get(user_id, {}).get('step') == 'awaiting_admin_username':
        username = update.message.text.strip()
        if not username.startswith("@"):
            await update.message.reply_text("❌ Имя пользователя должно начинаться с @")
            return

        await add_admin(0, username)
        await update.message.reply_text(f"✅ Админ {username} добавлен (требуется, чтобы он написал боту /start).")
        del ADMIN_USER_DATA[user_id]

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admins = await get_admins()
    if not admins:
        text = "📭 Нет администраторов."
    else:
        text = "📋 Список администраторов:\n" + "\n".join([f"• {username} (ID: {uid})" for uid, username in admins])
    await query.message.reply_text(text)

# === КОМАНДЫ ===

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"🔑 Ваш Telegram ID: `{user.id}`", parse_mode="Markdown")

async def cancel_any_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in USER_DATA:
        del USER_DATA[user_id]
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

# === ОБРАБОТЧИК КНОПОК ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    handlers_map = {
        # ТЗ
        "create_task": create_task_start,
        "confirm_task": confirm_task,
        "edit_task": edit_task,
        "cancel_task": cancel_task,
        
        # Баги
        "create_bug": create_bug_start,
        "confirm_bug": confirm_bug,
        "edit_bug": edit_bug,
        "cancel_bug": cancel_bug,
        "my_bugs_menu": my_bugs_menu,
        "admin_bugs_menu": admin_bugs_menu,
        
        # Заявки
        "apply_to_team": start_application,
        "apply_helper": set_position,
        "apply_moderator": set_position,
        "confirm_application": confirm_application,
        "edit_application": edit_application,
        "cancel_application": cancel_application,
        
        # Админ-панель
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
        await handle_admin_task_action(update, context)
    elif data.startswith("app_approve_") or data.startswith("app_reject_"):
        await handle_application_action(update, context)

# === ГЛАВНАЯ ФУНКЦИЯ ===

async def main():
    # Инициализация БД
    await init_db()

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("skip", skip_task_media))
    application.add_handler(CommandHandler("skip_bug", skip_bug_media))
    application.add_handler(CommandHandler("cancel", cancel_any_process))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("id", get_user_id))

    # Обработчики сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_text_message
    ))
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO) & filters.ChatType.PRIVATE,
        handle_media_message
    ))
    
    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ Бот запущен и готов к работе.")
    
    # Запускаем бота
    try:
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())