import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "telegram_chatbot")
    COLLECTION_MESSAGES = os.getenv("COLLECTION_MESSAGES", "messages")
    COLLECTION_CHATS = os.getenv("COLLECTION_CHATS", "active_chats")
    
    # Telegram API (for Telethon)
    TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    
    # AI
    AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
