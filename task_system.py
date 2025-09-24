# task_system.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *  # ✅ Исправлено: импортируем всё

logger = logging.getLogger(__name__)

# FSM для ТЗ
USER_DATA = {}

async def create_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("📝 Введите описание задачи:")

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_DATA.get(user_id, {}).get('step') == 'awaiting_description':
        USER_DATA[user_id]['description'] = update.message.text
        USER_DATA[user_id]['step'] = 'awaiting_media'
        await update.message.reply_text("📸 Прикрепите фото/видео (опционально) или отправьте /skip")

async def handle_media_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_DATA.get(user_id, {}).get('step') == 'awaiting_media':
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            USER_DATA[user_id]['media_file_id'] = file_id
        elif update.message.video:
            file_id = update.message.video.file_id
            USER_DATA[user_id]['media_file_id'] = file_id
        else:
            USER_DATA[user_id]['media_file_id'] = None

        desc = USER_DATA[user_id]['description']
        media = USER_DATA[user_id].get('media_file_id')

        text = f"🔍 Предпросмотр ТЗ:\n\n{desc}"
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_task")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="edit_task")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_task")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if media:
            if update.message.photo:
                await update.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
            elif update.message.video:
                await update.message.reply_video(video=media, caption=text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

        USER_DATA[user_id]['step'] = 'preview'

async def skip_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_media_or_skip(update, context)

async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_DATA:
        del USER_DATA[user_id]
        await query.message.reply_text("🚫 Создание ТЗ отменено.")
    else:
        await query.message.reply_text("ℹ️ Нет активного процесса.")

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

    admins = await get_admins()  # ✅ Теперь работает!
    sent_to_anyone = False

    for admin_id, username in admins:
        try:
            text = f"📄 Новое ТЗ от @{author_username}:\n\n{data['description']}"
            keyboard = [
                [
                    InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if data.get('media_file_id'):
                if update.effective_message.photo:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=data['media_file_id'],
                        caption=text,
                        reply_markup=reply_markup
                    )
                elif update.effective_message.video:
                    await context.bot.send_video(
                        chat_id=admin_id,
                        video=data['media_file_id'],
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
            logger.info(f"ТЗ #{task_id} отправлено админу {username} (ID: {admin_id})")
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {username} (ID: {admin_id}): {e}. Возможно, он не писал боту /start.")

    if not sent_to_anyone:
        await query.message.reply_text(
            "⚠️ Ни одному администратору не удалось отправить ТЗ.\n"
            "Убедитесь, что админы начали диалог с ботом — отправили ему команду /start."
        )
    else:
        await query.message.reply_text("✅ ТЗ успешно создано и отправлено администраторам!")

    del USER_DATA[user_id]

async def edit_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("✏️ Введите новое описание задачи:")

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def list_tasks_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str, title: str):
    query = update.callback_query
    user_id = update.effective_user.id

    is_user_admin = await is_admin(user_id)
    author_id = None if is_user_admin else user_id

    tasks = await get_tasks_by_status(status, author_id=author_id)

    if not tasks:
        await query.message.reply_text(f"📭 Нет {title.lower()}.")
        return

    for task in tasks:
        task_id, author, desc, media, _, admin, updated = task
        text = f"📌 ID: {task_id}\nАвтор: {author}\nОписание: {desc}\nСтатус: {title}"

        if admin:
            text += f"\nИсполнитель: {admin}"
        if updated:
            text += f"\nДата: {updated}"

        keyboard = []
        if status == "pending" and is_user_admin:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_id}")
                ]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        if media:
            try:
                await query.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
                continue
            except:
                pass
            try:
                await query.message.reply_video(video=media, caption=text, reply_markup=reply_markup)
                continue
            except:
                pass

        await query.message.reply_text(text, reply_markup=reply_markup)

async def list_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_tasks_by_status(update, context, "pending", "Активные задачи")

async def list_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_tasks_by_status(update, context, "completed", "Выполненные задачи")

async def list_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_tasks_by_status(update, context, "rejected", "Отклонённые задачи")