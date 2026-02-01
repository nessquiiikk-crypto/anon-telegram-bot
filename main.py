import os
import time
import logging
import sqlite3
import secrets

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_PATH = "anonq.sqlite3"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            owner_id INTEGER,
            text TEXT,
            created INTEGER
        )
    """)
    return conn


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == OWNER_ID:
        await update.message.reply_text(
            "Привет 🤍\n\n"
            "Команды:\n"
            "/link — получить ссылку для анонимных вопросов\n"
        )
        return

    if context.args:
        context.user_data["allow"] = True
        await update.message.reply_text("Напиши свой анонимный вопрос 💭")
    else:
        await update.message.reply_text("Тебе нужна специальная ссылка ✨")


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    bot = await context.bot.get_me()
    code = secrets.token_urlsafe(8)
    url = f"https://t.me/{bot.username}?start={code}"

    context.bot_data[code] = True

    await update.message.reply_text(
        "Твоя ссылка для анонимных вопросов:\n"
        f"{url}"
    )


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("allow"):
        return

    sender_id = update.effective_user.id
    text = update.message.text

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO messages(sender_id, owner_id, text, created) VALUES (?, ?, ?, ?)",
            (sender_id, OWNER_ID, text, int(time.time()))
        )
        msg_id = cur.lastrowid

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Ответить", callback_data=f"reply:{msg_id}")]
    ])

    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=f"📩 Анонимный вопрос:\n\n{text}",
        reply_markup=keyboard
    )

    await update.message.reply_text("Отправлено 💌")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != OWNER_ID:
        return

    msg_id = int(query.data.split(":")[1])
    context.user_data["reply_to"] = msg_id

    await query.message.reply_text("Напиши ответ ✍️")


async def reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "reply_to" not in context.user_data:
        return

    msg_id = context.user_data.pop("reply_to")
    answer = update.message.text

    with db() as conn:
        cur = conn.execute("SELECT sender_id FROM messages WHERE id=?", (msg_id,))
        row = cur.fetchone()

    if not row:
        await update.message.reply_text("Сообщение не найдено 😕")
        return

    sender_id = row[0]

    await context.bot.send_message(
        chat_id=sender_id,
        text=f"💬 Ответ:\n\n{answer}"
    )

    await update.message.reply_text("Ответ отправлен 🤍")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    app.run_polling()


if __name__ == "__main__":
    main()
