import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

from config import Config
from database import Database

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
    
    messages = db.get_messages(chat_id, limit=20)
    
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
    
    await update.callback_query.message.reply_text(
        f"🧹 **Data Cleared!**\n\n"
        f"✅ {result['messages_deleted']} messages deleted\n"
        f"✅ Chat removed from active list\n\n"
        f"*Start chatting again to save new data*",
        parse_mode="Markdown"
    )

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

# ---------- UTILITY FUNCTIONS ----------

def generate_response(message):
    """Generate simple response (Replace with AI later)"""
    msg = message.lower()
    
    if msg in ['hi', 'hello', 'hey', 'namaste']:
        return "👋 Hello! How can I help you today?"
    elif msg in ['bye', 'goodbye', 'tata']:
        return "👋 Goodbye! Come back anytime!"
    elif 'help' in msg:
        return "🆘 I'm here to help! Use /help to see all commands."
    elif 'joke' in msg:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾"
        ]
        import random
        return random.choice(jokes)
    elif 'how are you' in msg:
        return "🤖 I'm doing great! Thanks for asking. How can I assist you?"
    else:
        responses = [
            f"📝 I got your message: '{message[:50]}...'",
            "🤔 Interesting! Tell me more.",
            "💡 That's cool! What else?",
            "👍 Got it! Anything else I can help with?"
        ]
        import random
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
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    logger.info("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
