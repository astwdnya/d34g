import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv('API_ID', '23598202'))
API_HASH = os.getenv('API_HASH', '27c57538146f68a1c52a2651b51ec43c')
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Read from environment for security

# Optional: Use a Local Bot API server (to send files up to 2GB)
# If you run a local telegram-bot-api server, set these in your .env:
# BOT_API_BASE_URL=http://<host>:8081/bot
# BOT_API_BASE_FILE_URL=http://<host>:8081/file/bot
BOT_API_BASE_URL = os.getenv('BOT_API_BASE_URL')
BOT_API_BASE_FILE_URL = os.getenv('BOT_API_BASE_FILE_URL')
