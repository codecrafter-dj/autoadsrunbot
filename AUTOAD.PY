import os
import time
import asyncio
import glob
from datetime import datetime, timedelta
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from dotenv import load_dotenv
import warnings

# Configure warnings
warnings.filterwarnings("ignore", message="Server sent a very new message with ID")

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE_NUMBER')
MESSAGE = os.getenv('MESSAGE')
SESSION_FILE = 'session.session'

# Timing settings
GROUP_COOLDOWN = timedelta(hours=2)
INTER_GROUP_DELAY = 10
CHECK_INTERVAL = 60

def debug_print(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def clear_old_sessions():
    """Remove all old session files"""
    session_files = glob.glob('*.session') + glob.glob('*.session-journal')
    for file in session_files:
        try:
            os.remove(file)
            debug_print(f"Removed old session file: {file}")
        except Exception as e:
            debug_print(f"Error removing {file}: {e}")

class GroupSender:
    def __init__(self):
        clear_old_sessions()  # Clean up old sessions first
        self.client = TelegramClient(
            SESSION_FILE,
            API_ID,
            API_HASH,
            system_version="4.16.30-vxRETAIL"
        )
        self.running = True
        
    async def shutdown(self):
        """Properly shutdown the client"""
        self.running = False
        if self.client.is_connected():
            await self.client.disconnect()
            debug_print("Client disconnected")

    def run(self):
        try:
            with self.client:
                self.client.loop.run_until_complete(self.main())
        except KeyboardInterrupt:
            debug_print("Received exit signal, shutting down...")
            self.client.loop.run_until_complete(self.shutdown())
        except Exception as e:
            debug_print(f"Fatal error: {e}")
            self.client.loop.run_until_complete(self.shutdown())
        finally:
            # Clean up any pending tasks
            pending = asyncio.all_tasks(self.client.loop)
            for task in pending:
                task.cancel()
            debug_print("Cleanup complete")

    async def main(self):
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(PHONE)
                code = input('Enter the code you received: ')
                await self.client.sign_in(PHONE, code)
                debug_print("Successfully logged in")
            
            debug_print("Bot started successfully")
            group_timers = {}
            
            while self.running:
                try:
                    groups = await self.get_active_groups()
                    
                    for group in groups:
                        if not self.running:
                            break
                            
                        now = datetime.now()
                        
                        # Check cooldown
                        if group.id in group_timers and (now - group_timers[group.id] < GROUP_COOLDOWN):
                            continue
                        
                        # Send message with error handling
                        try:
                            await self.client.send_message(group.id, MESSAGE)
                            group_timers[group.id] = now
                            debug_print(f"Message sent to {group.title}")
                        except Exception as e:
                            if "Server sent a very new message" in str(e):
                                continue  # Silently ignore these warnings
                            debug_print(f"Error sending to {group.title}: {str(e)[:100]}...")
                        
                        await asyncio.sleep(INTER_GROUP_DELAY)
                    
                    await asyncio.sleep(CHECK_INTERVAL)
                    
                except Exception as e:
                    debug_print(f"Error in main loop: {str(e)[:100]}...")
                    await asyncio.sleep(60)
                    
        except Exception as e:
            debug_print(f"Main function error: {e}")
            raise

    async def get_active_groups(self):
        """Fetch active groups with error handling"""
        try:
            result = await self.client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            return [chat for chat in result.chats if hasattr(chat, 'megagroup') and chat.megagroup]
        except Exception as e:
            debug_print(f"Error fetching groups: {str(e)[:100]}...")
            return []

if __name__ == '__main__':
    debug_print("Starting bot...")
    bot = GroupSender()
    try:
        bot.run()
    except Exception as e:
        debug_print(f"Unhandled exception: {e}")
    finally:
        debug_print("Bot stopped")