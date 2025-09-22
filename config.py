import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = '7675664254:AAHL7QhPonc47z0QKRFnB5p_L15SRiLBddc'  # Your bot token

# Optional: Use a Local Bot API server (to send files up to 2GB)
# If you run a local telegram-bot-api server, set these in your .env:
# BOT_API_BASE_URL=http://<host>:8081/bot
# BOT_API_BASE_FILE_URL=http://<host>:8081/file/bot
BOT_API_BASE_URL = os.getenv('BOT_API_BASE_URL')
BOT_API_BASE_FILE_URL = os.getenv('BOT_API_BASE_FILE_URL')
