from pymongo import MongoClient
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.DATABASE_NAME]
        self.messages = self.db[Config.COLLECTION_MESSAGES]
        self.active_chats = self.db[Config.COLLECTION_CHATS]
        
        # Create indexes safely
        try:
            self.messages.create_index([("chat_id", 1), ("timestamp", -1)])
            self.messages.create_index("session_id")
            self.active_chats.create_index("chat_id", unique=True)
            # Fix: Use ASCENDING order for last_active
            self.active_chats.create_index([("last_active", -1)])
            logger.info("✅ MongoDB indexes created successfully")
        except Exception as e:
            logger.warning(f"⚠️ Index creation warning: {e}")
        
        logger.info("✅ Connected to MongoDB")

    # ---------- MESSAGE OPERATIONS ----------
    def save_message(self, chat_id, user_id, username, message, response="", 
                     session_id=None, intent=None, confidence=None):
        """Save a message to MongoDB"""
        doc = {
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "username": username,
            "message": message,
            "response": response,
            "session_id": session_id or f"session_{chat_id}_{int(datetime.now().timestamp())}",
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.utcnow()
        }
        result = self.messages.insert_one(doc)
        logger.info(f"💾 Message saved: {message[:50]}...")
        return result.inserted_id

    def get_messages(self, chat_id, limit=50, skip=0):
        """Get chat history"""
        cursor = self.messages.find(
            {"chat_id": str(chat_id)}
        ).sort("timestamp", -1).skip(skip).limit(limit)
        return list(cursor)

    def get_all_messages(self, chat_id):
        """Get all messages for a chat"""
        return list(self.messages.find({"chat_id": str(chat_id)}))

    def search_messages(self, chat_id, search_term):
        """Search messages by keyword"""
        cursor = self.messages.find({
            "chat_id": str(chat_id),
            "$or": [
                {"message": {"$regex": search_term, "$options": "i"}},
                {"response": {"$regex": search_term, "$options": "i"}}
            ]
        }).sort("timestamp", -1)
        return list(cursor)

    def get_message_count(self, chat_id):
        """Get total message count for a chat"""
        return self.messages.count_documents({"chat_id": str(chat_id)})

    # ---------- SESSION OPERATIONS ----------
    def get_session_messages(self, session_id, limit=50):
        """Get all messages for a specific session"""
        cursor = self.messages.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        return list(cursor)

    def get_last_session(self, chat_id):
        """Get last session for a chat"""
        result = self.messages.find_one(
            {"chat_id": str(chat_id)}
        ).sort("timestamp", -1)
        return result.get("session_id") if result else None

    # ---------- ACTIVE CHATS OPERATIONS ----------
    def save_active_chat(self, chat_id, username=None, first_name=None):
        """Save or update active chat"""
        now = datetime.utcnow()
        self.active_chats.update_one(
            {"chat_id": str(chat_id)},
            {
                "$setOnInsert": {
                    "first_seen": now,
                    "username": username,
                    "first_name": first_name
                },
                "$set": {
                    "last_active": now
                },
                "$inc": {"message_count": 1}
            },
            upsert=True
        )
        logger.info(f"👤 Active chat updated: {chat_id}")

    def get_active_chats(self, limit=50):
        """Get all active chats"""
        cursor = self.active_chats.find().sort("last_active", -1).limit(limit)
        return list(cursor)

    def get_chat_stats(self, chat_id):
        """Get statistics for a chat"""
        msg_count = self.messages.count_documents({"chat_id": str(chat_id)})
        chat_info = self.active_chats.find_one({"chat_id": str(chat_id)})
        return {
            "message_count": msg_count,
            "first_seen": chat_info.get("first_seen") if chat_info else None,
            "last_active": chat_info.get("last_active") if chat_info else None
        }

    # ---------- ANALYTICS ----------
    def get_analytics(self):
        """Get overall bot analytics"""
        total_chats = self.active_chats.count_documents({})
        total_messages = self.messages.count_documents({})
        return {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "most_active_chat": self.active_chats.find_one(
                sort=[("message_count", -1)]
            )
        }

    # ---------- DELETE OPERATIONS ----------
    def delete_chat_data(self, chat_id):
        """Delete all data for a chat"""
        msg_result = self.messages.delete_many({"chat_id": str(chat_id)})
        chat_result = self.active_chats.delete_one({"chat_id": str(chat_id)})
        return {
            "messages_deleted": msg_result.deleted_count,
            "chat_deleted": chat_result.deleted_count > 0
        }

    # ---------- TELEGRAM SESSION OPERATIONS ----------
    def save_telegram_session(self, phone, session_string):
        """Save Telegram session for message fetching"""
        collection = self.db["telegram_sessions"]
        collection.update_one(
            {"phone": phone},
            {"$set": {"session_string": session_string, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        logger.info(f"📱 Telegram session saved for {phone}")

    def get_telegram_session(self, phone):
        """Get Telegram session"""
        collection = self.db["telegram_sessions"]
        result = collection.find_one({"phone": phone})
        return result.get("session_string") if result else None

    def store_telegram_messages(self, chat_id, messages):
        """Store messages fetched from Telegram"""
        collection = self.db["telegram_fetched_messages"]
        for msg in messages:
            doc = {
                "chat_id": str(chat_id),
                "message_id": msg.id,
                "text": msg.text if hasattr(msg, 'text') else str(msg),
                "date": msg.date,
                "from_user": msg.from_user.username if msg.from_user else None,
                "stored_at": datetime.utcnow()
            }
            collection.update_one(
                {"chat_id": str(chat_id), "message_id": msg.id},
                {"$set": doc},
                upsert=True
            )
        logger.info(f"📥 Stored {len(messages)} messages from Telegram")
