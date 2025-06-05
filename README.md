import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
import yt_dlp

# Твой токен и админ ID
TOKEN = "6409245799:AAECfJLSS5-eeI-SOga9l7k4lmMn84RdG2g"
ADMIN_ID = 1979411532
SUBSCRIBERS_FILE = 'subscribers.json'

# Рекламная ссылка
AD_LINK = "\n\n🔥 Музыка тут: https://t.me/music6383"

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранение подписчиков
def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump(list(subscribers), f)

subscribers = load_subscribers()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in subscribers:
        subscribers.add(user_id)
        save_subscribers(subscribers)

    keyboard = [
        [InlineKeyboardButton("🌐 Язык", callback_data='lang')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Привет! Отправь мне название трека, и я найду его для тебя.",
        reply_markup=reply_markup
    )

# Смена языка
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🌍 Функция смены языка в разработке.")

# Поиск и отправка трека
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if user_id not in subscribers:
        subscribers.add(user_id)
        save_subscribers(subscribers)

    await update.message.reply_text("🔎 Ищу трек...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'outtmpl': 'music.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=True)
            title = info.get('title', 'Аудио')
            file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(audio, title=title, caption=AD_LINK)
        os.remove(file_path)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Не удалось найти трек.")

# Команда /sendall — рассылка
async def sendall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только админ может использовать эту команду.")
        return

    msg = update.message.text.split(maxsplit=1)
    if len(msg) < 2:
        await update.message.reply_text("⚠️ Используй: /sendall ТЕКСТ")
        return

    text = msg[1]
    sent = 0
    for user_id in list(subscribers):
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить пользователю {user_id}: {e}")

    await update.message.reply_text(f"✅ Отправлено {sent} пользователям.")

# /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(f"👥 Подписчиков: {len(subscribers)}")

# Запуск бота
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sendall", sendall))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
