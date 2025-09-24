# bug_system.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from config import GROUP_CHAT_ID, TOPIC_THREAD_ID_BUGS  # ✅ Исправлено

logger = logging.getLogger(__name__)

USER_BUG_DATA = {}

async def create_bug_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_BUG_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("🐞 Опишите баг (что сломалось, как воспроизвести):")

async def handle_bug_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_BUG_DATA.get(user_id, {}).get('step') == 'awaiting_description':
        USER_BUG_DATA[user_id]['description'] = update.message.text
        USER_BUG_DATA[user_id]['step'] = 'awaiting_media'
        await update.message.reply_text("📸 Прикрепите скриншот/видео (опционально) или /skip_bug")

async def skip_bug_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_bug_media_or_skip(update, context)

async def handle_bug_media_or_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_BUG_DATA.get(user_id, {}).get('step') == 'awaiting_media':
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            USER_BUG_DATA[user_id]['media_file_id'] = file_id
        elif update.message.video:
            file_id = update.message.video.file_id
            USER_BUG_DATA[user_id]['media_file_id'] = file_id
        else:
            USER_BUG_DATA[user_id]['media_file_id'] = None

        desc = USER_BUG_DATA[user_id]['description']
        media = USER_BUG_DATA[user_id].get('media_file_id')

        text = f"🔍 Предпросмотр бага:\n\n{desc}"
        keyboard = [
            [InlineKeyboardButton("✅ Отправить", callback_data="confirm_bug")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="edit_bug")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_bug")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if media:
            if update.message.photo:
                await update.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
            elif update.message.video:
                await update.message.reply_video(video=media, caption=text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

        USER_BUG_DATA[user_id]['step'] = 'preview'

async def cancel_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]
        await query.message.reply_text("🚫 Создание бага отменено.")
    else:
        await query.message.reply_text("ℹ️ Нет активного процесса.")

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
        logger.info(f"✅ Баг #{bug_id} создан в БД.")
    except Exception as e:
        logger.error(f"❌ Ошибка создания бага в БД: {e}")
        await query.message.reply_text("❌ Не удалось создать баг. Попробуйте позже.")
        return

    text = f"🐞 Баг #{bug_id} от @{author_username}:\n\n{data['description']}\n\nСтатус: ⏳ Ожидает обработки"

    keyboard = [
        [
            InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
            InlineKeyboardButton("🟡 Выполняется", callback_data=f"bug_progress_{bug_id}"),
            InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if data.get('media_file_id'):
            if update.effective_message.photo:
                sent_message = await context.bot.send_photo(
                    chat_id=GROUP_CHAT_ID,
                    message_thread_id=TOPIC_THREAD_ID_BUGS,  # ✅ Исправлено
                    photo=data['media_file_id'],
                    caption=text,
                    reply_markup=reply_markup
                )
            elif update.effective_message.video:
                sent_message = await context.bot.send_video(
                    chat_id=GROUP_CHAT_ID,
                    message_thread_id=TOPIC_THREAD_ID_BUGS,  # ✅ Исправлено
                    video=data['media_file_id'],
                    caption=text,
                    reply_markup=reply_markup
                )
        else:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=TOPIC_THREAD_ID_BUGS,  # ✅ Исправлено
                text=text,
                reply_markup=reply_markup
            )

        await update_bug_status(bug_id, "pending", 0, "system", sent_message.message_id)
        logger.info(f"✅ Баг #{bug_id} отправлен в группу (message_id={sent_message.message_id}).")
        await query.message.reply_text("✅ Баг отправлен в группу на рассмотрение!")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки бага в группу: {e}")
        await query.message.reply_text("❌ Не удалось отправить баг в группу. Проверьте настройки группы и темы.")

    if user_id in USER_BUG_DATA:
        del USER_BUG_DATA[user_id]

async def edit_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    USER_BUG_DATA[user_id] = {'step': 'awaiting_description'}
    await query.message.reply_text("✏️ Введите новое описание бага:")

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

    message_id_in_group = bug[7]

    await update_bug_status(bug_id, status, user_id, f"@{admin_username}")

    # ✅ Генерируем новую клавиатуру в зависимости от статуса
    keyboard = []
    if status == "in_progress":
        keyboard = [
            [
                InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
                InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
            ]
        ]
    elif status in ["completed", "rejected"]:
        keyboard = []
    else:
        keyboard = [
            [
                InlineKeyboardButton("🟢 Выполнено", callback_data=f"bug_complete_{bug_id}"),
                InlineKeyboardButton("🟡 Выполняется", callback_data=f"bug_progress_{bug_id}"),
                InlineKeyboardButton("🔴 Отклонено", callback_data=f"bug_reject_{bug_id}")
            ]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # Обновляем сообщение в группе
    if message_id_in_group:
        try:
            new_text = query.message.text.split("\n\nСтатус:")[0] + f"\n\nСтатус: {emoji} {status}"
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=message_id_in_group,
                text=new_text,
                reply_markup=reply_markup
            )
            logger.info(f"✅ Обновлено сообщение бага #{bug_id} в группе.")
        except Exception as e:
            logger.error(f"❌ Не удалось обновить сообщение бага в группе: {e}")

    # Уведомляем автора
    author_id = bug[1]
    desc = bug[3]
    try:
        await context.bot.send_message(
            chat_id=author_id,
            text=f"🔔 Ваш баг:\n\n{desc}\n\nизменил статус на: {emoji} {status} (администратор @{admin_username})"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось уведомить автора бага {author_id}: {e}")

    # Обновляем сообщение у админа (в личке)
    await query.message.edit_text(
        text=query.message.text.split("\n\nСтатус:")[0] + f"\n\nСтатус: {emoji} {status}",
        reply_markup=reply_markup
    )

async def list_bugs_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str, title: str):
    query = update.callback_query
    user_id = update.effective_user.id

    is_user_admin = await is_admin(user_id)
    author_id = None if is_user_admin else user_id

    bugs = await get_bugs_by_status(status, author_id=author_id)

    if not bugs:
        await query.message.reply_text(f"📭 Нет {title.lower()}.")
        return

    for bug in bugs:
        bug_id, author, desc, media, _, admin, updated, _ = bug
        text = f"🐞 ID: {bug_id}\nАвтор: {author}\nОписание: {desc}\nСтатус: {title}"

        if admin:
            text += f"\nИсполнитель: {admin}"
        if updated:
            text += f"\nДата: {updated}"

        await query.message.reply_text(text)

async def list_bugs_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_bugs_by_status(update, context, "pending", "Баги в ожидании")

async def list_bugs_in_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_bugs_by_status(update, context, "in_progress", "Баги в работе")

async def list_bugs_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_bugs_by_status(update, context, "completed", "Исправленные баги")

async def list_bugs_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_bugs_by_status(update, context, "rejected", "Отклонённые баги")