import logging
import asyncio
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

from config import Config
from database import Database
from telethon_session import TelegramMessageFetcher

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Database
db = Database()

# ---------- BOT HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - Register chat and show info"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Save to MongoDB
    db.save_active_chat(
        chat_id=chat_id,
        username=user.username,
        first_name=user.first_name
    )
    
    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("📊 My Stats", callback_data="stats"),
            InlineKeyboardButton("📝 History", callback_data="history")
        ],
        [
            InlineKeyboardButton("🧹 Clear Data", callback_data="clear"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 **Hello {user.first_name}!**\n\n"
        f"🤖 I'm your smart Telegram bot!\n"
        f"📌 **Your Chat ID:** `{chat_id}`\n\n"
        f"✅ All your messages will be saved in MongoDB\n"
        f"🔮 AI features coming soon!\n\n"
        f"*Use the buttons below or just start chatting!*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text
    username = user.username or user.first_name
    
    # Save user message
    db.save_message(
        chat_id=chat_id,
        user_id=user.id,
        username=username,
        message=text,
        response=""  # Will update later with AI response
    )
    
    # Update active chat
    db.save_active_chat(chat_id, username, user.first_name)
    
    # Simple response (replace with AI later)
    response = generate_response(text)
    
    # Update message with response
    db.messages.update_one(
        {"chat_id": str(chat_id), "message": text, "response": ""},
        {"$set": {"response": response}}
    )
    
    # Send reply
    await update.message.reply_text(response)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show chat history"""
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.callback_query.message.chat.id
    
    # Check if limit provided
    limit = 20
    if context.args:
        try:
            limit = int(context.args[0])
            if limit > 100:
                limit = 100
        except:
            pass
    
    messages = db.get_messages(chat_id, limit=limit)
    
    if not messages:
        text = "📭 No messages found in your history!"
    else:
        text = f"📜 **Last {len(messages)} Messages:**\n\n"
        for msg in reversed(messages):
            msg_text = msg.get('message', '')[:50]
            resp_text = msg.get('response', '')[:50] or 'No response'
            time = msg.get('timestamp', datetime.utcnow()).strftime("%H:%M")
            text += f"🕐 {time} | 👤 {msg_text}\n🤖 {resp_text}\n\n"
        
        if len(text) > 4000:
            text = text[:4000] + "...\n\n📌 Too many messages! Use /history <limit>"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show chat statistics"""
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.callback_query.message.chat.id
    
    stats_data = db.get_chat_stats(chat_id)
    analytics = db.get_analytics()
    
    text = f"""📊 **Your Statistics**

📝 Total Messages: {stats_data['message_count']}
🕐 First Seen: {stats_data['first_seen'].strftime('%Y-%m-%d %H:%M') if stats_data['first_seen'] else 'N/A'}
🕒 Last Active: {stats_data['last_active'].strftime('%Y-%m-%d %H:%M') if stats_data['last_active'] else 'N/A'}

🌐 **Bot Analytics**
👥 Total Active Chats: {analytics['total_chats']}
💬 Total Messages: {analytics['total_messages']}"""
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear chat data"""
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.callback_query.message.chat.id
    
    result = db.delete_chat_data(chat_id)
    
    text = f"🧹 **Data Cleared!**\n\n✅ {result['messages_deleted']} messages deleted\n✅ Chat removed from active list\n\n*Start chatting again to save new data*"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    if update.callback_query:
        await update.callback_query.answer()
    
    text = """🤖 **Bot Commands**

/start - Start bot and register chat
/history - Show chat history
/stats - View your statistics
/clear - Clear all your data
/help - Show this help

📌 **Features:**
• All messages saved in MongoDB
• Chat history stored
• Analytics and stats
• AI integration coming soon!

💡 **Pro Tip:** Use inline buttons for quick actions!"""
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

# ---------- TELEGRAM SESSION COMMANDS ----------

async def add_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add Telegram session for fetching messages"""
    chat_id = update.effective_chat.id
    
    # Check if admin
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "📱 **Add Telegram Session**\n\n"
            "Usage: `/addsession +91XXXXXXXXXX`\n\n"
            "Then verify using: `/verifycode <code>`",
            parse_mode="Markdown"
        )
        return
    
    phone = args[0]
    
    try:
        fetcher = TelegramMessageFetcher()
        result = await fetcher.create_session(phone)
        
        if result["status"] == "code_sent":
            await update.message.reply_text(
                f"✅ Code sent to {phone}\n"
                f"📲 Enter OTP: `/verifycode <code>`"
            )
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP code for session"""
    chat_id = update.effective_chat.id
    
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/verifycode <code>`", parse_mode="Markdown")
        return
    
    code = args[0]
    phone = Config.TELEGRAM_PHONE
    
    try:
        fetcher = TelegramMessageFetcher()
        result = await fetcher.verify_code(phone, code)
        
        if result["status"] == "success":
            await update.message.reply_text(
                f"✅ Session created successfully!\n"
                f"📌 Session: `{result['session']}`\n\n"
                f"Use `/fetchmsg <chat_id> <limit>` to fetch messages",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def fetch_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch messages from Telegram chat"""
    chat_id = update.effective_chat.id
    
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/fetchmsg <chat_id> <limit>`\n\n"
            "Example: `/fetchmsg -1001234567890 50`",
            parse_mode="Markdown"
        )
        return
    
    target_chat = args[0]
    limit = int(args[1]) if len(args) > 1 else 50
    
    try:
        await update.message.reply_text(f"🔄 Fetching {limit} messages from {target_chat}...")
        
        fetcher = TelegramMessageFetcher()
        result = await fetcher.fetch_messages(
            Config.TELEGRAM_PHONE,
            target_chat,
            limit
        )
        
        if result["status"] == "success":
            msg = f"✅ Fetched {result['count']} messages\n\n"
            for m in result["messages"][:10]:
                msg += f"📝 {m['from']}: {m['text'][:100]}\n"
            
            if len(msg) > 4000:
                msg = msg[:4000] + "...\n\n📌 Showing first 10 messages"
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def listen_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start listening to Telegram messages"""
    chat_id = update.effective_chat.id
    
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/listen <chat_id>`\n"
            "Example: `/listen -1001234567890`",
            parse_mode="Markdown"
        )
        return
    
    target_chat = args[0]
    
    await update.message.reply_text(f"👂 Listening to messages from {target_chat}...\nPress Ctrl+C to stop")
    
    try:
        fetcher = TelegramMessageFetcher()
        await fetcher.listen_messages(Config.TELEGRAM_PHONE, target_chat)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ---------- UTILITY FUNCTIONS ----------

def generate_response(message):
    """Generate simple response (Replace with AI later)"""
    msg = message.lower()
    
    if msg in ['hi', 'hello', 'hey', 'namaste', 'hii', 'hy']:
        return random.choice([
            "👋 Hello! How can I help you today?",
            "Hey there! 😊 What's up?",
            "Namaste! 🙏 Welcome!",
            "Hi! ✨ Good to see you!"
        ])
    elif msg in ['bye', 'goodbye', 'tata', 'bye bye']:
        return random.choice([
            "👋 Goodbye! Have a great day!",
            "Take care! 😊 Come back anytime!",
            "Bye! 🌟 Stay awesome!"
        ])
    elif 'help' in msg:
        return "🆘 I'm here to help! Use /help to see all commands."
    elif 'joke' in msg:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
            "What's a computer's favorite snack? Microchips! 🍟"
        ]
        return random.choice(jokes)
    elif 'how are you' in msg or 'how r u' in msg:
        return random.choice([
            "🤖 I'm doing great! Thanks for asking!",
            "I'm awesome! 💫 How about you?",
            "Feeling fantastic! 😊 Thanks!"
        ])
    elif 'thank' in msg:
        return random.choice([
            "You're welcome! 😊",
            "My pleasure! ✨",
            "Anytime! 🙌"
        ])
    elif 'what is your name' in msg or 'your name' in msg:
        return "🤖 I'm your friendly Telegram bot! You can call me Botty!"
    else:
        responses = [
            f"📝 Got it: '{message[:50]}...'",
            "🤔 Interesting! Tell me more.",
            "💡 That's cool! What else?",
            "👍 Got it! Anything else I can help with?",
            "😊 I'm listening! Go on...",
            "🤖 Processing... Done! What next?"
        ]
        return random.choice(responses)

# ---------- CALLBACK HANDLER ----------

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "stats":
        await stats(update, context)
    elif query.data == "history":
        await history(update, context)
    elif query.data == "clear":
        await clear_data(update, context)
    elif query.data == "help":
        await help_command(update, context)

# ---------- ERROR HANDLER ----------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ---------- MAIN ----------

def main():
    """Start the bot"""
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in .env file!")
        return
    
    logger.info("🚀 Starting bot...")
    
    # Create application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("clear", clear_data))
    app.add_handler(CommandHandler("help", help_command))
    
    # Telethon session commands
    app.add_handler(CommandHandler("addsession", add_session))
    app.add_handler(CommandHandler("verifycode", verify_code))
    app.add_handler(CommandHandler("fetchmsg", fetch_messages))
    app.add_handler(CommandHandler("listen", listen_messages))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🤖 Bot is running! Press Ctrl+C to stop.")
    logger.info(f"📊 Commands available: /start, /history, /stats, /clear, /help")
    logger.info(f"🔐 Admin commands: /addsession, /verifycode, /fetchmsg, /listen")
    app.run_polling()

if __name__ == "__main__":
    main()
