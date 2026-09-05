from pymongo import MongoClient
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            self.client = MongoClient(Config.MONGO_URI)
            self.db = self.client[Config.DATABASE_NAME]
            self.messages = self.db["messages"]
            self.active_chats = self.db["active_chats"]
            self.connection_status = self.db["connection_status"]
            
            # Create indexes for better performance
            self.messages.create_index([("chat_id", 1), ("timestamp", -1)])
            self.messages.create_index("session_id")
            self.active_chats.create_index("chat_id", unique=True)
            self.active_chats.create_index([("last_active", -1)])
            self.connection_status.create_index("chat_id", unique=True)
            
            logger.info("✅ MongoDB connected successfully!")
            logger.info(f"📊 Database: {Config.DATABASE_NAME}")
        except Exception as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            raise

    # ---------- MESSAGE OPERATIONS ----------
    def save_message(self, chat_id, user_id, username, message, response="", 
                     session_id=None, intent=None, confidence=None, msg_type="text"):
        """Save a message to MongoDB with type"""
        doc = {
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "username": username,
            "message": message,
            "response": response,
            "msg_type": msg_type,  # text, photo, document, video, audio, sticker, etc.
            "session_id": session_id or f"session_{chat_id}_{int(datetime.now().timestamp())}",
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.utcnow()
        }
        try:
            result = self.messages.insert_one(doc)
            logger.debug(f"💾 Message saved: {message[:30]}...")
            return result.inserted_id
        except Exception as e:
            logger.error(f"❌ Error saving message: {e}")
            return None

    def get_messages(self, chat_id, limit=50, skip=0):
        """Get chat history"""
        try:
            cursor = self.messages.find(
                {"chat_id": str(chat_id)}
            ).sort("timestamp", -1).skip(skip).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Error getting messages: {e}")
            return []

    def get_all_messages(self, chat_id):
        """Get all messages for a chat"""
        try:
            return list(self.messages.find({"chat_id": str(chat_id)}))
        except Exception as e:
            logger.error(f"❌ Error getting all messages: {e}")
            return []

    def search_messages(self, chat_id, search_term):
        """Search messages by keyword"""
        try:
            cursor = self.messages.find({
                "chat_id": str(chat_id),
                "$or": [
                    {"message": {"$regex": search_term, "$options": "i"}},
                    {"response": {"$regex": search_term, "$options": "i"}}
                ]
            }).sort("timestamp", -1)
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Error searching messages: {e}")
            return []

    def get_message_count(self, chat_id):
        """Get total message count for a chat"""
        try:
            return self.messages.count_documents({"chat_id": str(chat_id)})
        except Exception as e:
            logger.error(f"❌ Error getting message count: {e}")
            return 0

    def get_messages_by_type(self, chat_id, msg_type):
        """Get messages by type"""
        try:
            cursor = self.messages.find({
                "chat_id": str(chat_id),
                "msg_type": msg_type
            }).sort("timestamp", -1)
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Error getting messages by type: {e}")
            return []

    # ---------- SESSION OPERATIONS ----------
    def get_session_messages(self, session_id, limit=50):
        """Get all messages for a specific session"""
        try:
            cursor = self.messages.find(
                {"session_id": session_id}
            ).sort("timestamp", 1).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Error getting session messages: {e}")
            return []

    def get_last_session(self, chat_id):
        """Get last session for a chat"""
        try:
            result = self.messages.find_one(
                {"chat_id": str(chat_id)}
            ).sort("timestamp", -1)
            return result.get("session_id") if result else None
        except Exception as e:
            logger.error(f"❌ Error getting last session: {e}")
            return None

    # ---------- ACTIVE CHATS OPERATIONS ----------
    def save_active_chat(self, chat_id, username=None, first_name=None):
        """Save or update active chat"""
        try:
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
            logger.debug(f"👤 Active chat updated: {chat_id}")
        except Exception as e:
            logger.error(f"❌ Error saving active chat: {e}")

    def get_active_chats(self, limit=50):
        """Get all active chats"""
        try:
            cursor = self.active_chats.find().sort("last_active", -1).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Error getting active chats: {e}")
            return []

    def get_chat_stats(self, chat_id):
        """Get statistics for a chat"""
        try:
            msg_count = self.messages.count_documents({"chat_id": str(chat_id)})
            chat_info = self.active_chats.find_one({"chat_id": str(chat_id)})
            return {
                "message_count": msg_count,
                "first_seen": chat_info.get("first_seen") if chat_info else None,
                "last_active": chat_info.get("last_active") if chat_info else None
            }
        except Exception as e:
            logger.error(f"❌ Error getting chat stats: {e}")
            return {"message_count": 0, "first_seen": None, "last_active": None}

    # ---------- ANALYTICS ----------
    def get_analytics(self):
        """Get overall bot analytics"""
        try:
            total_chats = self.active_chats.count_documents({})
            total_messages = self.messages.count_documents({})
            return {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "most_active_chat": self.active_chats.find_one(
                    sort=[("message_count", -1)]
                )
            }
        except Exception as e:
            logger.error(f"❌ Error getting analytics: {e}")
            return {"total_chats": 0, "total_messages": 0, "most_active_chat": None}

    # ---------- CONNECTION STATUS ----------
    def set_connection_status(self, chat_id, is_active):
        """Set connection status for a chat"""
        try:
            self.connection_status.update_one(
                {"chat_id": str(chat_id)},
                {
                    "$set": {
                        "is_active": is_active,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            logger.info(f"🔗 Connection status for {chat_id}: {is_active}")
        except Exception as e:
            logger.error(f"❌ Error setting connection status: {e}")

    def get_connection_status(self, chat_id):
        """Get connection status for a chat"""
        try:
            result = self.connection_status.find_one({"chat_id": str(chat_id)})
            return result.get("is_active", False) if result else False
        except Exception as e:
            logger.error(f"❌ Error getting connection status: {e}")
            return False

    # ---------- DELETE OPERATIONS ----------
    def delete_chat_data(self, chat_id):
        """Delete all data for a chat"""
        try:
            msg_result = self.messages.delete_many({"chat_id": str(chat_id)})
            chat_result = self.active_chats.delete_one({"chat_id": str(chat_id)})
            self.connection_status.delete_one({"chat_id": str(chat_id)})
            return {
                "messages_deleted": msg_result.deleted_count,
                "chat_deleted": chat_result.deleted_count > 0
            }
        except Exception as e:
            logger.error(f"❌ Error deleting chat data: {e}")
            return {"messages_deleted": 0, "chat_deleted": False}

    def delete_old_messages(self, days=30):
        """Delete messages older than specified days"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            result = self.messages.delete_many({"timestamp": {"$lt": cutoff}})
            logger.info(f"🧹 Deleted {result.deleted_count} old messages")
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ Error deleting old messages: {e}")
            return 0

    # ---------- UTILITY ----------
    def get_collection_stats(self):
        """Get collection statistics"""
        try:
            return {
                "messages": self.messages.count_documents({}),
                "active_chats": self.active_chats.count_documents({}),
                "connection_status": self.connection_status.count_documents({})
            }
        except Exception as e:
            logger.error(f"❌ Error getting collection stats: {e}")
            return {}

    def drop_collection(self, collection_name):
        """Drop a collection (use with caution)"""
        try:
            if collection_name in ["messages", "active_chats", "connection_status"]:
                self.db[collection_name].drop()
                logger.warning(f"🗑️ Dropped collection: {collection_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error dropping collection: {e}")
            return False
