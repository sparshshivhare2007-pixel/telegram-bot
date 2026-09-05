from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
from config import Config
from database import Database
import logging

logger = logging.getLogger(__name__)

class TelegramMessageFetcher:
    def __init__(self):
        self.db = Database()
        self.api_id = Config.TELEGRAM_API_ID
        self.api_hash = Config.TELEGRAM_API_HASH
        self.session_string = None
        self.client = None

    async def create_session(self, phone_number):
        """Create a new Telegram session"""
        try:
            # Create client
            self.client = TelegramClient(StringSession(), self.api_id, self.api_hash)
            await self.client.connect()
            
            # Send code
            await self.client.send_code_request(phone_number)
            logger.info(f"📱 Code sent to {phone_number}")
            
            return {"status": "code_sent", "phone": phone_number}
        except Exception as e:
            logger.error(f"❌ Session creation error: {e}")
            return {"status": "error", "error": str(e)}

    async def verify_code(self, phone_number, code):
        """Verify code and get session string"""
        try:
            self.client = TelegramClient(StringSession(), self.api_id, self.api_hash)
            await self.client.connect()
            
            # Sign in with code
            await self.client.sign_in(phone_number, code)
            
            # Save session string
            session_string = self.client.session.save()
            self.db.save_telegram_session(phone_number, session_string)
            
            logger.info(f"✅ Session created for {phone_number}")
            return {"status": "success", "session": session_string[:20] + "..."}
        except Exception as e:
            logger.error(f"❌ Verification error: {e}")
            return {"status": "error", "error": str(e)}

    async def fetch_messages(self, phone_number, chat_id, limit=50):
        """Fetch messages from a specific chat"""
        try:
            # Get session
            session_string = self.db.get_telegram_session(phone_number)
            if not session_string:
                logger.error("❌ No session found")
                return {"status": "error", "error": "Session not found"}
            
            # Connect
            self.client = TelegramClient(StringSession(session_string), self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                return {"status": "error", "error": "Not authorized"}
            
            # Get messages
            entity = await self.client.get_entity(int(chat_id))
            messages = await self.client.get_messages(entity, limit=limit)
            
            # Store in MongoDB
            self.db.store_telegram_messages(chat_id, messages)
            
            return {
                "status": "success",
                "messages": [
                    {
                        "id": msg.id,
                        "text": msg.text[:100] if msg.text else "[Media]",
                        "date": msg.date.isoformat(),
                        "from": msg.from_user.username if msg.from_user else "Unknown"
                    }
                    for msg in messages
                ],
                "count": len(messages)
            }
        except Exception as e:
            logger.error(f"❌ Fetch error: {e}")
            return {"status": "error", "error": str(e)}

    async def listen_messages(self, phone_number, chat_id):
        """Listen to new messages and store them"""
        try:
            session_string = self.db.get_telegram_session(phone_number)
            if not session_string:
                return {"status": "error", "error": "Session not found"}
            
            self.client = TelegramClient(StringSession(session_string), self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                return {"status": "error", "error": "Not authorized"}
            
            entity = await self.client.get_entity(int(chat_id))
            
            @self.client.on(events.NewMessage(chats=entity))
            async def handler(event):
                # Store message
                msg = event.message
                self.db.store_telegram_messages(
                    chat_id, 
                    [msg]
                )
                logger.info(f"📥 New message from {chat_id}: {msg.text[:50] if msg.text else '[Media]'}")
            
            logger.info(f"👂 Listening to messages from {chat_id}")
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"❌ Listen error: {e}")
            return {"status": "error", "error": str(e)}

# ---------- CLI for Session Creation ----------
async def create_telethon_session():
    """CLI to create Telegram session"""
    print("📱 Telegram Session Creator")
    print("=" * 30)
    
    api_id = input("Enter API ID: ")
    api_hash = input("Enter API Hash: ")
    phone = input("Enter Phone Number (with country code): ")
    
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        # Send code
        await client.send_code_request(phone)
        print("✅ Code sent!")
        
        code = input("Enter verification code: ")
        await client.sign_in(phone, code)
        
        session_string = client.session.save()
        print(f"\n✅ Session created successfully!")
        print(f"📌 Session String: {session_string[:50]}...")
        
        # Save to file
        with open("telegram_session.txt", "w") as f:
            f.write(session_string)
        print("💾 Session saved to telegram_session.txt")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(create_telethon_session())
