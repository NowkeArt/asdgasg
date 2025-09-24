# database.py
import aiosqlite
import logging

logger = logging.getLogger(__name__)

DB_PATH = "tasks.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Админы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Технические задания
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                author_username TEXT NOT NULL,
                description TEXT NOT NULL,
                media_file_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_admin_id INTEGER,
                assigned_admin_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Баги
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                author_username TEXT NOT NULL,
                description TEXT NOT NULL,
                media_file_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_admin_id INTEGER,
                assigned_admin_username TEXT,
                message_id_in_group INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Заявки в команду
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                position TEXT NOT NULL,
                timezone TEXT,
                moderation_experience TEXT,
                other_projects TEXT,
                cheat_check_knowledge TEXT,
                grif_experience TEXT,
                age TEXT,
                available_time TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                message_id_in_group INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def add_admin(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()
        logger.info(f"Добавлен админ: {username} (ID: {user_id})")

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def get_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username FROM admins") as cursor:
            return await cursor.fetchall()

# === Функции для ТЗ ===

async def create_task(author_id: int, author_username: str, description: str, media_file_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO tasks
            (author_id, author_username, description, media_file_id)
            VALUES (?, ?, ?, ?)""",
            (author_id, author_username, description, media_file_id)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0]

async def update_task_status(task_id: int, status: str, admin_id: int, admin_username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE tasks
            SET status = ?, assigned_admin_id = ?, assigned_admin_username = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (status, admin_id, admin_username, task_id)
        )
        await db.commit()

async def get_tasks_by_status(status: str, author_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if author_id:
            query = "SELECT id, author_username, description, media_file_id, status, assigned_admin_username, updated_at FROM tasks WHERE status = ? AND author_id = ?"
            params = (status, author_id)
        else:
            query = "SELECT id, author_username, description, media_file_id, status, assigned_admin_username, updated_at FROM tasks WHERE status = ?"
            params = (status,)
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_task_by_id(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, author_id, author_username, description, media_file_id, status, assigned_admin_username, updated_at FROM tasks WHERE id = ?",
            (task_id,)
        ) as cursor:
            return await cursor.fetchone()

# === Функции для багов ===

async def create_bug(author_id: int, author_username: str, description: str, media_file_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO bugs
            (author_id, author_username, description, media_file_id)
            VALUES (?, ?, ?, ?)""",
            (author_id, author_username, description, media_file_id)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0]

async def update_bug_status(bug_id: int, status: str, admin_id: int, admin_username: str, message_id_in_group: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if message_id_in_group:
            await db.execute(
                """UPDATE bugs
                SET status = ?, assigned_admin_id = ?, assigned_admin_username = ?, message_id_in_group = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (status, admin_id, admin_username, message_id_in_group, bug_id)
            )
        else:
            await db.execute(
                """UPDATE bugs
                SET status = ?, assigned_admin_id = ?, assigned_admin_username = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (status, admin_id, admin_username, bug_id)
            )
        await db.commit()

async def get_bug_by_id(bug_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, author_id, author_username, description, media_file_id, status, assigned_admin_username, message_id_in_group FROM bugs WHERE id = ?",
            (bug_id,)
        ) as cursor:
            return await cursor.fetchone()

async def get_bugs_by_status(status: str, author_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if author_id:
            query = "SELECT id, author_username, description, media_file_id, status, assigned_admin_username, updated_at, message_id_in_group FROM bugs WHERE status = ? AND author_id = ?"
            params = (status, author_id)
        else:
            query = "SELECT id, author_username, description, media_file_id, status, assigned_admin_username, updated_at, message_id_in_group FROM bugs WHERE status = ?"
            params = (status,)
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

# === Функции для заявок ===

async def get_last_application(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def create_application(user_id, username, position, answers):
    tz, mod_exp, other_proj, cheat_check, grif_exp, age, time_avail = answers
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO applications
            (user_id, username, position, timezone, moderation_experience, other_projects,
             cheat_check_knowledge, grif_experience, age, available_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, position, tz, mod_exp, other_proj, cheat_check, grif_exp, age, time_avail)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0]

async def get_application_by_id(app_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
            return await cursor.fetchone()

async def update_application_status(app_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, app_id)
        )
        await db.commit()

async def update_application_message_id(app_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE applications SET message_id_in_group = ? WHERE id = ?",
            (message_id, app_id)
        )
        await db.commit()