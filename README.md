import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Проверяем и устанавливаем нужные библиотеки
try:
    import telegram
    import yt_dlp
    import flask
except ImportError:
    print("Устанавливаю нужные библиотеки...")
    install("python-telegram-bot")
    install("yt-dlp")
    install("flask")
    print("Библиотеки установлены. Перезапустите скрипт.")
    sys.exit()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import json, os, yt_dlp, asyncio
from threading import Thread
from flask import Flask

TOKEN = "6409245799:AAECfJLSS5-eeI-SOga9l7k4lmMn84RdG2g"
ADMIN_ID = 1979411532
ADVERTISEMENT = "\n\n🎧 Музыку ищи тут: https://t.me/music6383"

LANGUAGES = {
    "ru": {
        "start": "👋 Привет! Отправь мне название трека, и я помогу найти музыку.",
        "language": "🇷🇺 Язык переключён на русский.",
        "results": "🔎 Вот что я нашёл. Выбери трек:",
        "no_results": "❌ Ничего не найдено.",
        "sending": "🎶 Отправляю...",
        "sent_all": "✅ Сообщение отправлено всем подписчикам.",
        "not_admin": "⛔ Команда только для администратора.",
        "enter_message": "✏️ Введите сообщение для рассылки:"
    },
    "en": {
        "start": "👋 Hello! Send me a track name and I'll help you find music.",
        "language": "🇬🇧 Language switched to English.",
        "results": "🔎 Here are the results. Choose a track:",
        "no_results": "❌ Nothing found.",
        "sending": "🎶 Sending...",
        "sent_all": "✅ Message sent to all subscribers.",
        "not_admin": "⛔ Command only for admin.",
        "enter_message": "✏️ Enter the message to broadcast:"
    }
}

USERS_FILE = "users.json"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f)

def add_user(user_id):
    data = load_users()
    if str(user_id) not in data:
        data[str(user_id)] = {"lang": "ru"}
        save_users(data)

def get_lang(user_id):
    data = load_users()
    return data.get(str(user_id), {}).get("lang", "ru")

def set_lang(user_id, lang):
    data = load_users()
    if str(user_id) in data:
        data[str(user_id)]["lang"] = lang
        save_users(data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_user(uid)
    lang = get_lang(uid)
    keyboard = [[InlineKeyboardButton("🌐 Язык", callback_data="change_lang")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(LANGUAGES[lang]["start"], reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    if query.data == "change_lang":
        new_lang = "en" if lang == "ru" else "ru"
        set_lang(uid, new_lang)
        await query.edit_message_text(text=LANGUAGES[new_lang]["language"])

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    uid = update.effective_user.id
    add_user(uid)
    lang = get_lang(uid)

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
        'default_search': 'ytsearch5',
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" not in info or not info["entries"]:
                await update.message.reply_text(LANGUAGES[lang]["no_results"])
                return
            results = info["entries"]
            buttons = [[InlineKeyboardButton(entry["title"][:50], callback_data=f"play_{entry['url']}")] for entry in results]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(LANGUAGES[lang]["results"], reply_markup=reply_markup)
    except Exception as e:
        print(e)
        await update.message.reply_text("⚠️ Ошибка при поиске.")

async def handle_sendall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(LANGUAGES[get_lang(update.effective_user.id)]["not_admin"])
        return
    context.user_data["sendall"] = True
    await update.message.reply_text(LANGUAGES[get_lang(update.effective_user.id)]["enter_message"])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get("sendall"):
        context.user_data["sendall"] = False
        msg = update.message.text
        users = load_users()
        sent = 0
        for user_id in users:
            try:
                await context.bot.send_message(chat_id=int(user_id), text=msg)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                continue
        await update.message.reply_text(f"✅ Отправлено: {sent}")
    else:
        await message(update, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(LANGUAGES[get_lang(update.effective_user.id)]["not_admin"])
        return
    count = len(load_users())
    await update.message.reply_text(f"👥 Подписчиков: {count}")

async def play_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data.replace("play_", "")
    uid = query.from_user.id
    lang = get_lang(uid)

    await query.edit_message_text(LANGUAGES[lang]["sending"])
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'song.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "track")
            file_path = "song.mp3"
            caption = f"{title}{ADVERTISEMENT}"
            await context.bot.send_audio(chat_id=uid, audio=open(file_path, 'rb'), title=title, caption=caption)
            os.remove(file_path)
    except Exception as e:
        print(e)
        await context.bot.send_message(chat_id=uid, text="⚠️ Ошибка при загрузке трека.")

# ---- keep_alive в этом же файле ----
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "✅ Бот работает 24/7"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ------------------------------

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sendall", handle_sendall))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button, pattern="change_lang"))
    app.add_handler(CallbackQueryHandler(play_track, pattern="play_"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()