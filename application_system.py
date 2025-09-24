# application_system.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from config import GROUP_CHAT_ID, TOPIC_THREAD_ID_APPS
import aiosqlite
import asyncio

logger = logging.getLogger(__name__)

DB_PATH = "tasks.db"

USER_APPLICATION = {}

QUESTIONS = [
    "1. Ваш часовой пояс?",
    "2. Есть ли опыт модерации? Если да, то укажите проект и длительность поста.",
    "3. Состоите ли Вы на данный момент в администрации/модерации/команде на ином проекте?",
    "4. Знаете ли Вы, как проводить проверку на читы?",
    "5. Общий Опыт/Длительность игры на серверах типу Анка/Гриф?",
    "6. Ваш возраст?",
    "7. Время, которое вы готовы выделять на сервер в день (можно указать промежуток времени и дни)."
]

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    username = update.effective_user.username or f"user{user_id}"

    # Проверка: подавал ли заявку за последние 7 дней?
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
    tz, mod_exp, other_proj, cheat_check, grif_exp, age, time_avail = app_data['answers']

    # Сохраняем в БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO applications
            (user_id, username, position, timezone, moderation_experience, other_projects,
             cheat_check_knowledge, grif_experience, age, available_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, f"@{username}", app_data['position'], tz, mod_exp, other_proj, cheat_check, grif_exp, age, time_avail)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            app_id = row[0]

    # Отправка в ОТДЕЛЬНУЮ тему для заявок
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

    try:
        sent_message = await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            message_thread_id=TOPIC_THREAD_ID_APPS,  # ← Отдельная тема!
            text=text,
            reply_markup=reply_markup
        )
        # Сохраняем message_id
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE applications SET message_id_in_group = ? WHERE id = ?",
                (sent_message.message_id, app_id)
            )
            await db.commit()
        await query.message.reply_text("✅ Ваша заявка отправлена! Ожидайте решения.")
    except Exception as e:
        logger.error(f"Ошибка отправки заявки в группу: {e}")
        await query.message.reply_text("❌ Не удалось отправить заявку. Попробуйте позже.")

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
    else:
        await query.message.reply_text("ℹ️ Нет активной заявки.")

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

    # Получаем заявку
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
            app = await cursor.fetchone()
    if not app:
        await query.message.reply_text("❌ Заявка не найдена.")
        return

    # Обновляем статус
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, app_id)
        )
        await db.commit()

    # Уведомляем автора
    author_id = app[1]
    try:
        await context.bot.send_message(chat_id=author_id, text=message)
    except Exception as e:
        logger.error(f"Не удалось уведомить автора заявки {author_id}: {e}")

    # Обновляем сообщение в группе
    message_id_in_group = app[12]
    if message_id_in_group:
        try:
            new_text = query.message.text + f"\n\n📌 Статус: {'ОДОБРЕНО' if status == 'approved' else 'ОТКЛОНЕНО'}"
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=message_id_in_group,
                text=new_text,
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение заявки в группе: {e}")

    await query.message.edit_text(
        text=query.message.text + f"\n\n📌 Статус: {'ОДОБРЕНО' if status == 'approved' else 'ОТКЛОНЕНО'}",
        reply_markup=None
    )

# Вспомогательная функция: последняя заявка
async def get_last_application(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()