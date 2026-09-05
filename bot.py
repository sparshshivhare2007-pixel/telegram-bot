import logging
import random
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes
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

# Store active chats in memory
active_chats = set()

# ---------- BOT HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Save to MongoDB
    db.save_active_chat(
        chat_id=chat_id,
        username=user.username,
        first_name=user.first_name
    )
    
    await update.message.reply_text(
        f"👋 **Hello {user.first_name}!**\n\n"
        f"🤖 Bot is active!\n"
        f"📌 **Chat ID:** `{chat_id}`\n\n"
        f"✅ All messages will be saved in MongoDB\n"
        f"🔗 Use `/connect` to start storing messages\n"
        f"🔗 Use `/disconnect` to stop storing messages",
        parse_mode="Markdown"
    )

async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect bot to store messages"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Check if admin
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    # Add to active chats
    active_chats.add(str(chat_id))
    
    # Save to database
    db.save_active_chat(
        chat_id=chat_id,
        username=user.username,
        first_name=user.first_name
    )
    
    # Save connection status
    db.set_connection_status(chat_id, True)
    
    await update.message.reply_text(
        f"✅ **Bot Connected!**\n\n"
        f"📌 Chat ID: `{chat_id}`\n"
        f"📝 All messages will now be stored\n\n"
        f"Use `/disconnect` to stop storing messages",
        parse_mode="Markdown"
    )
    
    logger.info(f"🔗 Bot connected to chat {chat_id}")

async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disconnect bot from storing messages"""
    chat_id = update.effective_chat.id
    
    # Check if admin
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    # Remove from active chats
    active_chats.discard(str(chat_id))
    
    # Update database
    db.set_connection_status(chat_id, False)
    
    await update.message.reply_text(
        f"❌ **Bot Disconnected!**\n\n"
        f"📌 Chat ID: `{chat_id}`\n"
        f"⏹️ Messages will no longer be stored",
        parse_mode="Markdown"
    )
    
    logger.info(f"🔌 Bot disconnected from chat {chat_id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages and store them"""
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    message = update.message
    
    # Check if chat is active for storing
    if chat_id not in active_chats:
        return
    
    # Get message text and type
    if message.text:
        msg_type = "text"
        content = message.text
    elif message.photo:
        msg_type = "photo"
        content = f"[Photo] {message.caption or ''}"
    elif message.document:
        msg_type = "document"
        content = f"[Document] {message.document.file_name or 'Unknown'}"
    elif message.video:
        msg_type = "video"
        content = f"[Video] {message.video.file_name or 'Unknown'}"
    elif message.audio:
        msg_type = "audio"
        content = f"[Audio] {message.audio.file_name or 'Unknown'}"
    elif message.sticker:
        msg_type = "sticker"
        content = f"[Sticker] {message.sticker.emoji or 'Unknown'}"
    elif message.voice:
        msg_type = "voice"
        content = "[Voice message]"
    elif message.video_note:
        msg_type = "video_note"
        content = "[Video note]"
    elif message.location:
        msg_type = "location"
        content = f"[Location] Lat: {message.location.latitude}, Lon: {message.location.longitude}"
    elif message.contact:
        msg_type = "contact"
        content = f"[Contact] {message.contact.first_name} {message.contact.last_name or ''}"
    else:
        msg_type = "unknown"
        content = "[Unknown message type]"
    
    # Get sender info
    username = user.username or user.first_name or "Unknown"
    user_id = user.id
    
    # Save to database
    db.save_message(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        message=content,
        response="",
        msg_type=msg_type
    )
    
    # Update active chat stats
    db.save_active_chat(
        chat_id=chat_id,
        username=username,
        first_name=user.first_name
    )
    
    # Log
    logger.info(f"💾 Message stored from {chat_id}: {content[:50]}...")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    chat_id = str(update.effective_chat.id)
    
    is_active = chat_id in active_chats
    stats = db.get_chat_stats(chat_id)
    
    status_text = "🟢 Active" if is_active else "🔴 Inactive"
    
    await update.message.reply_text(
        f"📊 **Bot Status**\n\n"
        f"📌 Chat ID: `{chat_id}`\n"
        f"🔗 Status: {status_text}\n"
        f"📝 Messages Stored: {stats['message_count']}\n\n"
        f"Use `/connect` to activate\n"
        f"Use `/disconnect` to deactivate",
        parse_mode="Markdown"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent messages"""
    chat_id = str(update.effective_chat.id)
    
    # Check admin
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    messages = db.get_messages(chat_id, limit=20)
    
    if not messages:
        await update.message.reply_text("📭 No messages found!")
        return
    
    text = f"📜 **Last {len(messages)} Messages:**\n\n"
    for msg in reversed(messages):
        msg_text = msg.get('message', '')[:50]
        time = msg.get('timestamp', datetime.utcnow()).strftime("%H:%M")
        username = msg.get('username', 'Unknown')
        msg_type = msg.get('msg_type', 'text')
        text += f"🕐 {time} | 👤 {username} [{msg_type}]: {msg_text}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "...\n\n📌 Too many messages!"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def stats_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show overall bot statistics"""
    chat_id = str(update.effective_chat.id)
    
    # Check admin
    if str(chat_id) != Config.ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    analytics = db.get_analytics()
    
    text = f"""📊 **Overall Statistics**

👥 Total Active Chats: {analytics['total_chats']}
💬 Total Messages: {analytics['total_messages']}

📋 **Active Chats:**
"""
    
    chats = db.get_active_chats(limit=10)
    for chat in chats:
        text += f"• Chat ID: `{chat['chat_id']}` - {chat.get('message_count', 0)} messages\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    await update.message.reply_text(
        f"🤖 **Bot Commands**\n\n"
        f"/start - Start the bot\n"
        f"/connect - Start storing messages\n"
        f"/disconnect - Stop storing messages\n"
        f"/status - Check bot status\n"
        f"/history - Show recent messages (admin only)\n"
        f"/statsall - Show overall stats (admin only)\n"
        f"/help - Show this help\n\n"
        f"📌 **Features:**\n"
        f"• Stores all messages in MongoDB\n"
        f"• Works in groups and DMs\n"
        f"• Stores text, photos, documents, videos, audio, stickers, voice, location, contacts\n"
        f"• Admin control to start/stop\n\n"
        f"💡 **Tip:** Add bot to any group and use /connect to start storing!",
        parse_mode="Markdown"
    )

# ---------- MAIN ----------

def main():
    """Start the bot"""
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in .env file!")
        return
    
    logger.info("🚀 Starting bot...")
    logger.info(f"📊 MongoDB: {Config.MONGO_URI[:30]}...")
    
    # Create application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("statsall", stats_all))
    app.add_handler(CommandHandler("help", help_command))
    
    # Message handler - stores all messages
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND, 
        handle_message
    ))
    
    # Start bot
    logger.info("🤖 Bot is running! Press Ctrl+C to stop.")
    logger.info("📌 Use /connect to start storing messages")
    logger.info("📌 Use /disconnect to stop storing messages")
    app.run_polling()

if __name__ == "__main__":
    main()
