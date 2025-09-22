import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Read from environment for security

# Optional: Use a Local Bot API server (to send files up to 2GB)
# If you run a local telegram-bot-api server, set these in your .env:
# BOT_API_BASE_URL=http://<host>:8081/bot
# BOT_API_BASE_FILE_URL=http://<host>:8081/file/bot
BOT_API_BASE_URL = os.getenv('BOT_API_BASE_URL')
BOT_API_BASE_FILE_URL = os.getenv('BOT_API_BASE_FILE_URL')

# Optional: Free large-file workaround without Local Bot API
# Generate a Pyrogram session string locally and set TG_SESSION_STRING,
# and create a private channel, add both your user and the bot as admins,
# then set its ID as BRIDGE_CHANNEL_ID.
TG_SESSION_STRING = os.getenv('TG_SESSION_STRING')
BRIDGE_CHANNEL_ID = int(os.getenv('BRIDGE_CHANNEL_ID', '0'))
