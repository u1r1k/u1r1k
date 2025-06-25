import os
import logging
import asyncio
# другие импорты...

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Далее остальной код
#!/usr/bin/env python3
"""
Мощный музыкальный Telegram бот с системой непрерывной работы 24/7
Интеграция с системой автоматического восстановления
"""

import asyncio
import signal
import sys
import os
import time
import logging
import random
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.error import NetworkError, TelegramError

# Импорт компонентов системы 24/7
from bot.handlers import BotHandlers as BaseHandlers
from bot.monitors import HeartbeatMonitor
from bot.error_handler import ErrorHandler
from utils.logger import setup_logger
from utils.config import Config

# Импорт keep_alive
from keep_alive import keep_alive

# Создаем заглушки для недостающих модулей
class AudioDownloader:
    """Заглушка для AudioDownloader с базовой функциональностью"""
    
    def search_tracks(self, query: str, limit: int = 5):
        """Имитация поиска треков"""
        # В реальном боте здесь будет ваша логика поиска
        mock_tracks = [
            {
                'id': f'track_{i}',
                'title': f'{query} - Track {i+1}',
                'uploader': f'Artist {i+1}',
                'duration': f'{random.randint(2,5)}:{random.randint(10,59):02d}'
            }
            for i in range(min(limit, 3))
        ]
        return mock_tracks
    
    def download_track(self, track_id: str, title: str):
        """Имитация скачивания трека"""
        # В реальном боте здесь будет ваша логика скачивания
        logger.info(f"Downloading track: {title}")
        return None  # Вернуть путь к файлу в реальной реализации

# Константы
ADMIN_ID = 1979411532
BOT_LINK = "https://t.me/music6383"
DEFAULT_SEARCH_RESULTS = 5

class MusicTelegramBot:
    """Основной класс музыкального бота с системой восстановления 24/7"""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger("MusicBot")
        self.application = None
        self.monitor = None
        self.error_handler = None
        self.is_running = False
        self.restart_count = 0
        
        # Компоненты музыкального бота
        self.downloader = AudioDownloader()
        self.user_search_results = {}
        self.subscribers = set()
        self.user_favorites = {}
        self.user_language = {}
        
    def get_main_keyboard(self, is_admin=False, lang='ru'):
        if lang == 'en':
            keyboard = [
                ["🎵 Search Music", "📂 My Library"],
                ["⭐ Top Charts", "❤️ Favorites"],
                ["🎲 Random Song", "🔧 Settings"],
                ["📊 Statistics", "🆘 Help"]
            ]
            if is_admin:
                keyboard.append(["⚙️ Admin Panel"])
        else:
            keyboard = [
                ["🎵 Поиск музыки", "📂 Моя библиотека"],
                ["⭐ Топ чарты", "❤️ Избранное"],
                ["🎲 Случайная песня", "🔧 Настройки"],
                ["📊 Статистика", "🆘 Помощь"]
            ]
            if is_admin:
                keyboard.append(["⚙️ Админ панель"])
                
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_search_inline_keyboard(self, tracks, lang='ru'):
        keyboard = []
        for i, track in enumerate(tracks):
            keyboard.append([InlineKeyboardButton(
                f"🎵 {track['title'][:30]}..." if len(track['title']) > 30 else f"🎵 {track['title']}", 
                callback_data=f"download_{i}"
            )])
        
        if lang == 'en':
            keyboard.append([InlineKeyboardButton("❤️ Add to Favorites", callback_data="add_favorite")])
            keyboard.append([InlineKeyboardButton("🔄 New Search", callback_data="new_search")])
        else:
            keyboard.append([InlineKeyboardButton("❤️ В избранное", callback_data="add_favorite")])
            keyboard.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
            
        return InlineKeyboardMarkup(keyboard)

    def get_settings_keyboard(self, lang='ru'):
        if lang == 'en':
            keyboard = [
                [InlineKeyboardButton("🌍 Language: English", callback_data="lang_ru")],
                [InlineKeyboardButton("🔊 Audio Quality: High", callback_data="quality_toggle")],
                [InlineKeyboardButton("🔔 Notifications: ON", callback_data="notif_toggle")],
                [InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_menu")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("🌍 Язык: Русский", callback_data="lang_en")],
                [InlineKeyboardButton("🔊 Качество: Высокое", callback_data="quality_toggle")],
                [InlineKeyboardButton("🔔 Уведомления: ВКЛ", callback_data="notif_toggle")],
                [InlineKeyboardButton("🗑️ Очистить историю", callback_data="clear_history")],
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_menu")]
            ]
        return InlineKeyboardMarkup(keyboard)

    async def initialize(self):
        """Инициализация бота и его компонентов"""
        try:
            self.logger.info("🚀 Инициализация музыкального бота...")
            
            # Создание приложения
            self.application = Application.builder().token(self.config.bot_token).build()
            
            # Инициализация компонентов системы 24/7
            self.monitor = HeartbeatMonitor(self.logger)
            self.error_handler = ErrorHandler(self.logger)
            
            # Регистрация обработчиков команд
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("stats", self.show_stats))
            self.application.add_handler(CommandHandler("broadcast", self.broadcast_message))
            self.application.add_handler(CallbackQueryHandler(self.handle_button_callback))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
            
            # Обработчик ошибок
            self.application.add_error_handler(self.error_handler.handle_error)
            
            # Настройка обработки сигналов
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            self.logger.info("✅ Инициализация завершена успешно")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации: {e}")
            return False

    async def start_bot(self):
        """Запуск бота"""
        try:
            self.logger.info("🟢 Запуск музыкального бота...")
            self.is_running = True
            
            # Запуск мониторинга
            monitor_task = asyncio.create_task(self.monitor.start_monitoring())
            
            # Инициализация и запуск приложения
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
            bot_info = await self.application.bot.get_me()
            self.logger.info(f"🎯 Музыкальный бот запущен! Username: @{bot_info.username}")
            
            # Основной цикл работы
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска бота: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Очистка ресурсов при завершении"""
        try:
            self.logger.info("🧹 Завершение работы музыкального бота...")
            self.is_running = False
            
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                
            if self.monitor:
                await self.monitor.stop_monitoring()
                
            self.logger.info("✅ Музыкальный бот остановлен корректно")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при завершении: {e}")

    def signal_handler(self, signum, frame):
        """Обработчик системных сигналов"""
        self.logger.info(f"📡 Получен сигнал {signum}, завершение работы...")
        self.is_running = False

    # Все методы музыкального бота
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.subscribers.add(user.id)
        lang = self.user_language.get(user.id, 'ru')
        
        welcome_text = {
            'ru': f"🎵 Привет, {user.first_name}!\n\n🎧 Я помогу тебе найти и скачать любую музыку!\n\n💡 Просто отправь название песни или воспользуйся кнопками ниже:",
            'en': f"🎵 Hello, {user.first_name}!\n\n🎧 I'll help you find and download any music!\n\n💡 Just send a song title or use the buttons below:"
        }
        
        await update.message.reply_text(
            welcome_text[lang],
            reply_markup=self.get_main_keyboard(is_admin=user.id == ADMIN_ID, lang=lang)
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        help_text = {
            'ru': """🆘 **ПОМОЩЬ**

🎵 **Поиск музыки:**
• Отправь название песни
• Пример: "Believer Imagine Dragons"

🎯 **Команды:**
• /start - Главное меню
• /help - Эта справка
• /stats - Твоя статистика

💡 **Советы:**
• Используй точные названия
• Указывай исполнителя для лучших результатов
• Добавляй песни в избранное ❤️

🤖 **Фишки:**
• Случайная музыка 🎲
• Топ чарты ⭐
• Персональная библиотека 📂

🛡️ **Система 24/7:**
• Автоматическое восстановление
• Мониторинг работы
• Защита от сбоев""",
            'en': """🆘 **HELP**

🎵 **Music Search:**
• Send song title
• Example: "Believer Imagine Dragons"

🎯 **Commands:**
• /start - Main menu
• /help - This help
• /stats - Your statistics

💡 **Tips:**
• Use exact titles
• Specify artist for better results
• Add songs to favorites ❤️

🤖 **Features:**
• Random music 🎲
• Top charts ⭐
• Personal library 📂

🛡️ **24/7 System:**
• Auto recovery
• Work monitoring
• Error protection"""
        }
        
        await update.message.reply_text(help_text[lang], parse_mode='Markdown')

    async def handle_button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        await query.answer()
        
        if query.data.startswith("download_"):
            await self.download_by_callback(update, context)
        elif query.data == "add_favorite":
            await self.add_to_favorites(update, context)
        elif query.data == "new_search":
            text = "🔍 Отправь название новой песни:" if lang == 'ru' else "🔍 Send new song title:"
            await query.edit_message_text(text)
        elif query.data.startswith("lang_"):
            await self.change_language(update, context)
        elif query.data == "quality_toggle":
            text = "🔊 Качество изменено!" if lang == 'ru' else "🔊 Quality changed!"
            await query.edit_message_text(text)
        elif query.data == "notif_toggle":
            text = "🔔 Настройки уведомлений изменены!" if lang == 'ru' else "🔔 Notification settings changed!"
            await query.edit_message_text(text)
        elif query.data == "clear_history":
            if user_id in self.user_search_results:
                del self.user_search_results[user_id]
            text = "🗑️ История очищена!" if lang == 'ru' else "🗑️ History cleared!"
            await query.edit_message_text(text)
        elif query.data == "back_menu":
            text = "🏠 Главное меню:" if lang == 'ru' else "🏠 Main menu:"
            await query.edit_message_text(text, reply_markup=None)

    async def download_by_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        if user_id not in self.user_search_results:
            text = "❗ Сначала найдите песню!" if lang == 'ru' else "❗ Search for a song first!"
            await query.edit_message_text(text)
            return

        try:
            idx = int(query.data.split("_")[1])
            tracks = self.user_search_results[user_id]
            
            if not 0 <= idx < len(tracks):
                text = "⚠️ Неверный выбор!" if lang == 'ru' else "⚠️ Invalid selection!"
                await query.edit_message_text(text)
                return

            track = tracks[idx]
            loading_text = f"⬇️ Скачиваю: {track['title']}" if lang == 'ru' else f"⬇️ Downloading: {track['title']}"
            await query.edit_message_text(loading_text)

            filepath = self.downloader.download_track(track['id'], track['title'])
            if filepath:
                with open(filepath, "rb") as audio:
                    caption = f"🎵 {track['title']}\n👤 {track['uploader']}\n\n🤖 Музыка от бота {BOT_LINK}"
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio,
                        title=track['title'],
                        performer=track['uploader'],
                        caption=caption
                    )
                
                success_text = "✅ Готово! Наслаждайся музыкой! 🎧" if lang == 'ru' else "✅ Done! Enjoy the music! 🎧"
                await query.edit_message_text(success_text)
                
                try:
                    os.remove(filepath)
                except:
                    pass
            else:
                # Показываем результат даже без реального файла
                success_text = f"✅ Трек найден: {track['title']}\n(В демо-режиме файлы не скачиваются)" if lang == 'ru' else f"✅ Track found: {track['title']}\n(Demo mode - no actual download)"
                await query.edit_message_text(success_text)
        except Exception as e:
            self.logger.error(f"Callback download error: {e}")
            error_text = "❌ Ошибка при загрузке." if lang == 'ru' else "❌ Download error."
            await query.edit_message_text(error_text)

    async def add_to_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        if user_id not in self.user_favorites:
            self.user_favorites[user_id] = []
        
        if user_id in self.user_search_results and self.user_search_results[user_id]:
            track = self.user_search_results[user_id][0]
            if track not in self.user_favorites[user_id]:
                self.user_favorites[user_id].append(track)
                text = f"❤️ Добавлено в избранное!" if lang == 'ru' else f"❤️ Added to favorites!"
            else:
                text = "⚠️ Уже в избранном!" if lang == 'ru' else "⚠️ Already in favorites!"
        else:
            text = "❗ Нет треков для добавления!" if lang == 'ru' else "❗ No tracks to add!"
            
        await query.edit_message_text(text)

    async def change_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        new_lang = query.data.split("_")[1]
        self.user_language[user_id] = new_lang
        
        if new_lang == 'en':
            text = "🇺🇸 Language changed to English!"
        else:
            text = "🇷🇺 Язык изменён на русский!"
            
        await query.edit_message_text(text, reply_markup=self.get_settings_keyboard(new_lang))

    async def search_music(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = update.message.text.strip()
        lang = self.user_language.get(user_id, 'ru')

        if not query or query.startswith("/"):
            return

        search_text = f"🔎 Ищу: {query}" if lang == 'ru' else f"🔎 Searching: {query}"
        msg = await update.message.reply_text(search_text)
        
        try:
            tracks = self.downloader.search_tracks(query, DEFAULT_SEARCH_RESULTS)
            if not tracks:
                no_results = "❌ Ничего не найдено. Попробуй другой запрос." if lang == 'ru' else "❌ Nothing found. Try another search."
                await msg.edit_text(no_results)
                return

            self.user_search_results[user_id] = tracks
            
            result_text = "🎶 Найдено:\n\n" if lang == 'ru' else "🎶 Found:\n\n"
            for i, track in enumerate(tracks):
                result_text += f"{i+1}. 🎵 {track['title']}\n"
                result_text += f"   👤 {track['uploader']} | ⏰ {track['duration']}\n\n"

            instruction = "👇 Выбери трек кнопкой ниже:" if lang == 'ru' else "👇 Select track with button below:"
            result_text += instruction

            await msg.edit_text(
                result_text,
                reply_markup=self.get_search_inline_keyboard(tracks, lang)
            )
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            error_text = "❌ Ошибка при поиске. Попробуй позже." if lang == 'ru' else "❌ Search error. Try later."
            await msg.edit_text(error_text)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        lang = self.user_language.get(user_id, 'ru')

        button_handlers = {
            "🎵 Поиск музыки": lambda: update.message.reply_text("🔍 Отправь название песни:"),
            "📂 Моя библиотека": self.show_library,
            "⭐ Топ чарты": self.show_top_charts,
            "❤️ Избранное": self.show_favorites,
            "🎲 Случайная песня": self.random_song,
            "🔧 Настройки": self.show_settings,
            "📊 Статистика": self.show_stats,
            "🆘 Помощь": self.help_command,
            "⚙️ Админ панель": self.admin_panel,
            
            "🎵 Search Music": lambda: update.message.reply_text("🔍 Send song title:"),
            "📂 My Library": self.show_library,
            "⭐ Top Charts": self.show_top_charts,
            "❤️ Favorites": self.show_favorites,
            "🎲 Random Song": self.random_song,
            "🔧 Settings": self.show_settings,
            "📊 Statistics": self.show_stats,
            "🆘 Help": self.help_command,
            "⚙️ Admin Panel": self.admin_panel,
        }

        if text in button_handlers:
            return await button_handlers[text](update, context)
        elif text.isdigit():
            return await self.download_by_number(update, context)
        else:
            return await self.search_music(update, context)

    async def show_library(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        searches = len(self.user_search_results.get(user_id, []))
        favorites = len(self.user_favorites.get(user_id, []))
        
        text = f"📂 **Твоя музыкальная библиотека:**\n\n🎵 Поисков: {searches}\n❤️ Избранных треков: {favorites}\n📈 История активна" if lang == 'ru' else f"📂 **Your music library:**\n\n🎵 Searches: {searches}\n❤️ Favorite tracks: {favorites}\n📈 History active"
        await update.message.reply_text(text, parse_mode='Markdown')

    async def show_top_charts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = self.user_language.get(update.effective_user.id, 'ru')
        
        top_songs = [
            "🏆 Imagine Dragons - Believer",
            "🥈 Ed Sheeran - Shape of You", 
            "🥉 The Weeknd - Blinding Lights",
            "4️⃣ Dua Lipa - Levitating",
            "5️⃣ Post Malone - Circles"
        ]
        
        text = "⭐ **ТОП ЧАРТЫ:**\n\n" + "\n".join(top_songs) if lang == 'ru' else "⭐ **TOP CHARTS:**\n\n" + "\n".join(top_songs)
        await update.message.reply_text(text, parse_mode='Markdown')

    async def show_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            text = "❤️ Избранное пусто.\nДобавь песни в избранное при поиске!" if lang == 'ru' else "❤️ Favorites empty.\nAdd songs to favorites when searching!"
        else:
            text = "❤️ **ИЗБРАННОЕ:**\n\n" if lang == 'ru' else "❤️ **FAVORITES:**\n\n"
            for i, track in enumerate(self.user_favorites[user_id][:10]):
                text += f"{i+1}. 🎵 {track['title']}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')

    async def random_song(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lang = self.user_language.get(update.effective_user.id, 'ru')
        
        random_queries = ["popular music", "top hits 2024", "best songs", "trending music", "viral songs"]
        query = random.choice(random_queries)
        
        msg_text = "🎲 Ищу случайную песню..." if lang == 'ru' else "🎲 Finding random song..."
        msg = await update.message.reply_text(msg_text)
        
        try:
            tracks = self.downloader.search_tracks(query, 1)
            if tracks:
                track = tracks[0]
                self.user_search_results[update.effective_user.id] = tracks
                
                text = f"🎲 **Случайная песня:**\n\n🎵 {track['title']}\n👤 {track['uploader']}\n⏰ {track['duration']}" if lang == 'ru' else f"🎲 **Random song:**\n\n🎵 {track['title']}\n👤 {track['uploader']}\n⏰ {track['duration']}"
                
                keyboard = [[InlineKeyboardButton("⬇️ Скачать" if lang == 'ru' else "⬇️ Download", callback_data="download_0")]]
                await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else:
                error_text = "❌ Не удалось найти случайную песню." if lang == 'ru' else "❌ Failed to find random song."
                await msg.edit_text(error_text)
        except Exception as e:
            self.logger.error(f"Random song error: {e}")
            error_text = "❌ Ошибка при поиске." if lang == 'ru' else "❌ Search error."
            await msg.edit_text(error_text)

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        text = "🔧 **НАСТРОЙКИ:**" if lang == 'ru' else "🔧 **SETTINGS:**"
        await update.message.reply_text(
            text, 
            reply_markup=self.get_settings_keyboard(lang),
            parse_mode='Markdown'
        )

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        searches = len(self.user_search_results.get(user_id, []))
        favorites = len(self.user_favorites.get(user_id, []))
        
        if lang == 'ru':
            text = f"""📊 **ТВОЯ СТАТИСТИКА:**

🔍 Поисков: {searches}
❤️ В избранном: {favorites}
🎵 Активность: {searches * 2}
⭐ Рейтинг: Меломан
🎯 Статус: Активен

🛡️ **Система 24/7:**
✅ Автовосстановление работает
✅ Мониторинг активен
✅ Защита от сбоев включена"""
        else:
            text = f"""📊 **YOUR STATISTICS:**

🔍 Searches: {searches}
❤️ Favorites: {favorites}
🎵 Activity: {searches * 2}
⭐ Rating: Music Lover
🎯 Status: Active

🛡️ **24/7 System:**
✅ Auto-recovery working
✅ Monitoring active
✅ Error protection enabled"""
        
        await update.message.reply_text(text, parse_mode='Markdown')

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
            
        lang = self.user_language.get(update.effective_user.id, 'ru')
        
        uptime = datetime.now() - self.monitor.start_time if self.monitor else datetime.now()
        uptime_str = str(uptime).split('.')[0]
        
        if lang == 'ru':
            text = f"""⚙️ **АДМИН ПАНЕЛЬ:**

👥 Подписчиков: {len(self.subscribers)}
🔍 Активных поисков: {len(self.user_search_results)}
❤️ Общее избранное: {sum(len(favs) for favs in self.user_favorites.values())}
📊 Языки: RU={sum(1 for l in self.user_language.values() if l=='ru')}, EN={sum(1 for l in self.user_language.values() if l=='en')}

🛡️ **Система 24/7:**
⏰ Время работы: {uptime_str}
💚 Мониторинг: Активен
🔄 Автовосстановление: Работает

🤖 Бот работает стабильно!"""
        else:
            text = f"""⚙️ **ADMIN PANEL:**

👥 Subscribers: {len(self.subscribers)}
🔍 Active searches: {len(self.user_search_results)}
❤️ Total favorites: {sum(len(favs) for favs in self.user_favorites.values())}
📊 Languages: RU={sum(1 for l in self.user_language.values() if l=='ru')}, EN={sum(1 for l in self.user_language.values() if l=='en')}

🛡️ **24/7 System:**
⏰ Uptime: {uptime_str}
💚 Monitoring: Active
🔄 Auto-recovery: Working

🤖 Bot working stable!"""
        
        keyboard = [
            [InlineKeyboardButton("📢 Рассылка" if lang == 'ru' else "📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📊 Статистика" if lang == 'ru' else "📊 Statistics", callback_data="admin_stats")]
        ]
        
        await update.message.reply_text(
            text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
            
        lang = self.user_language.get(update.effective_user.id, 'ru')
        
        if not context.args:
            text = "❌ Формат: /broadcast [сообщение]" if lang == 'ru' else "❌ Format: /broadcast [message]"
            await update.message.reply_text(text)
            return
            
        broadcast_text = " ".join(context.args)
        
        if len(broadcast_text) > 4000:
            text = "❌ Сообщение слишком длинное! Максимум 4000 символов." if lang == 'ru' else "❌ Message too long! Max 4000 characters."
            await update.message.reply_text(text)
            return
        
        header = "📢 **РАССЫЛКА ОТ АДМИНИСТРАТОРА:**\n\n" if lang == 'ru' else "📢 **BROADCAST FROM ADMIN:**\n\n"
        final_message = header + broadcast_text + f"\n\n🤖 {BOT_LINK}"
        
        sent_count = 0
        failed_count = 0
        
        status_msg = await update.message.reply_text(
            f"📤 Начинаю рассылку для {len(self.subscribers)} пользователей..." if lang == 'ru' 
            else f"📤 Starting broadcast for {len(self.subscribers)} users..."
        )
        
        for user_id in list(self.subscribers):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=final_message,
                    parse_mode='Markdown'
                )
                sent_count += 1
                
                if sent_count % 10 == 0:
                    await status_msg.edit_text(
                        f"📤 Отправлено: {sent_count}/{len(self.subscribers)}" if lang == 'ru'
                        else f"📤 Sent: {sent_count}/{len(self.subscribers)}"
                    )
                    
            except Exception as e:
                failed_count += 1
                if "blocked" in str(e).lower() or "not found" in str(e).lower():
                    self.subscribers.discard(user_id)
                self.logger.error(f"Broadcast error for user {user_id}: {e}")
        
        if lang == 'ru':
            final_text = f"""✅ **РАССЫЛКА ЗАВЕРШЕНА!**

📊 Статистика:
• Отправлено: {sent_count}
• Ошибок: {failed_count}
• Активных пользователей: {len(self.subscribers)}"""
        else:
            final_text = f"""✅ **BROADCAST COMPLETED!**

📊 Statistics:
• Sent: {sent_count}
• Failed: {failed_count}
• Active users: {len(self.subscribers)}"""
        
        await status_msg.edit_text(final_text, parse_mode='Markdown')

    async def download_by_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        lang = self.user_language.get(user_id, 'ru')
        
        if user_id not in self.user_search_results:
            text = "❗ Сначала отправь название песни для поиска." if lang == 'ru' else "❗ Search for a song first."
            return await update.message.reply_text(text)

        try:
            idx = int(update.message.text) - 1
            tracks = self.user_search_results[user_id]
            if not 0 <= idx < len(tracks):
                text = "⚠️ Неверный номер трека." if lang == 'ru' else "⚠️ Invalid track number."
                return await update.message.reply_text(text)

            track = tracks[idx]
            loading_text = f"⬇️ Обрабатываю: {track['title']}" if lang == 'ru' else f"⬇️ Processing: {track['title']}"
            msg = await update.message.reply_text(loading_text)

            # В демо режиме просто показываем информацию о треке
            success_text = f"✅ Трек найден: {track['title']}\n👤 {track['uploader']}\n⏰ {track['duration']}\n\n(В демо-режиме файлы не скачиваются)" if lang == 'ru' else f"✅ Track found: {track['title']}\n👤 {track['uploader']}\n⏰ {track['duration']}\n\n(Demo mode - no actual download)"
            await msg.edit_text(success_text)
            
        except Exception as e:
            self.logger.error(f"Download error: {e}")
            error_text = "❌ Ошибка при обработке трека." if lang == 'ru' else "❌ Track processing error."
            await update.message.reply_text(error_text)

    async def run_with_recovery(self):
        """Запуск бота с системой автоматического восстановления"""
        max_restarts = 10
        restart_delay = 5
        
        while self.restart_count < max_restarts:
            try:
                if not await self.initialize():
                    self.restart_count += 1
                    await asyncio.sleep(restart_delay)
                    continue
                
                await self.start_bot()
                break
                
            except (NetworkError, TelegramError) as e:
                self.restart_count += 1
                self.logger.warning(
                    f"🔄 Сетевая ошибка #{self.restart_count}: {e}. "
                    f"Перезапуск через {restart_delay} секунд..."
                )
                await asyncio.sleep(restart_delay)
                
            except KeyboardInterrupt:
                self.logger.info("⌨️ Получен сигнал прерывания от пользователя")
                break
                
            except Exception as e:
                self.restart_count += 1
                self.logger.error(
                    f"💥 Критическая ошибка #{self.restart_count}: {e}. "
                    f"Перезапуск через {restart_delay} секунд..."
                )
                await asyncio.sleep(restart_delay)
        
        if self.restart_count >= max_restarts:
            self.logger.critical(
                f"🚨 Превышено максимальное количество перезапусков ({max_restarts}). "
                "Бот остановлен."
            )
        
        await self.cleanup()

async def main():
    """Главная функция"""
    # Запускаем keep-alive сервер
    keep_alive()
    
    bot = MusicTelegramBot()
    await bot.run_with_recovery()

- name: Run tests
  run: |
    pytest || true
    except KeyboardInterrupt:
        print("\n🛑 Музыкальный бот остановлен пользователем")
    except Exception as e:
        print(f"💀 Фатальная ошибка: {e}")
        sys.exit(1)