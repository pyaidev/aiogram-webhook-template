# utils/db.py
import aiosqlite
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Create database directory if it doesn't exist
DATABASE_DIR = Path("./data/db")
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# Database file path
DB_PATH = DATABASE_DIR / "test.db"

async def ensure_db_exists():
    """
    Ensure the database and tables exist
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Create users table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            email TEXT,
            access_token TEXT,
            refresh_token TEXT,
            calendar_connected BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await db.commit()

async def save_user_tokens(user_id, chat_id=None, email=None, access_token=None, refresh_token=None):
    """
    Сохраняем токены пользователя в базе данных. Обновляет только переданные поля.
    """
    await ensure_db_exists()


    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT user_id, refresh_token FROM users WHERE user_id = ?', (user_id,))
        user = await cursor.fetchone()

        if user:
            old_refresh_token = user[1] if user else None
            refresh_token = refresh_token or old_refresh_token  # Не затираем старый refresh_token

            update_fields = []
            update_values = []

            if chat_id is not None:
                update_fields.append("chat_id = ?")
                update_values.append(chat_id)
            if email is not None:
                update_fields.append("email = ?")
                update_values.append(email)
            if access_token is not None:
                update_fields.append("access_token = ?")
                update_values.append(access_token)

            update_fields.append("refresh_token = ?")
            update_values.append(refresh_token)

            update_values.append(user_id)
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"

            await db.execute(query, update_values)
            print(f"[🛠] Updated tokens for user {user_id}. New access_token: {access_token}, refresh_token: {refresh_token}")

        else:
            if access_token and refresh_token:
                await db.execute('''
                INSERT INTO users (user_id, chat_id, email, access_token, refresh_token)
                VALUES (?, ?, ?, ?, ?)
                ''', (user_id, chat_id, email, access_token, refresh_token))
                print(f"[➕] Inserted new user {user_id} with tokens.")

        await db.commit()



async def update_calendar_connected(user_id, is_connected=True):
    """
    Update the calendar_connected status for a user
    """
    await ensure_db_exists()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
        UPDATE users 
        SET calendar_connected = ?
        WHERE user_id = ?
        ''', (1 if is_connected else 0, user_id))
        
        await db.commit()
        return True

async def get_user_tokens(user_id):
    """
    Get user tokens from the database
    """
    await ensure_db_exists()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
        SELECT user_id, chat_id, email, access_token, refresh_token, calendar_connected
        FROM users
        WHERE user_id = ?
        ''', (user_id,))
        
        row = await cursor.fetchone()
        
        if row:
            return {
                'user_id': row[0],
                'chat_id': row[1],
                'email': row[2],
                'access_token': row[3],
                'refresh_token': row[4],
                'calendar_connected': bool(row[5])
            }
        return None

async def get_all_active_users():
    """
    Get all users with valid tokens and connected calendars
    """
    await ensure_db_exists()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
        SELECT user_id, chat_id, access_token, refresh_token
        FROM users
        WHERE access_token IS NOT NULL AND calendar_connected = 1
        ''')
        
        rows = await cursor.fetchall()
        
        return [
            {
                'user_id': row[0],
                'chat_id': row[1], 
                'access_token': row[2],
                'refresh_token': row[3]
            }
            for row in rows
        ]
        
async def get_user_tokens_by_access_token(access_token):
    """
    Найти пользователя по access_token и получить refresh_token
    """
    await ensure_db_exists()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
        SELECT user_id, refresh_token 
        FROM users 
        WHERE access_token = ?
        ''', (access_token,))
        
        row = await cursor.fetchone()
        
        if row:
            return {'user_id': row[0], 'refresh_token': row[1]}
        
        print(f"[❌] User with access_token {access_token} not found in database!")
        return None
