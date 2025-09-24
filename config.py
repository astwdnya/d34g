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

# Authorization settings
_auth_users_raw = os.getenv('AUTHORIZED_USERS', '').strip()
AUTHORIZED_USERS = set()
if _auth_users_raw:
    try:
        AUTHORIZED_USERS = {int(x.strip()) for x in _auth_users_raw.split(',') if x.strip()}
    except Exception:
        # Ignore parse errors; will fall back to defaults in bot.py
        AUTHORIZED_USERS = set()

ALLOW_ALL = os.getenv('ALLOW_ALL', 'false').lower() in {'1', 'true', 'yes', 'on'}

# yt-dlp / YouTube configuration
# Optional: Provide cookies to bypass login/anti-bot prompts
# YT_COOKIES_FILE: absolute path to a Netscape cookies.txt file inside the container
# YT_COOKIES_B64: base64-encoded contents of a Netscape cookies.txt; will be written to /tmp/yt_cookies.txt
YT_COOKIES_FILE = os.getenv('YT_COOKIES_FILE')
YT_COOKIES_B64 = os.getenv('YT_COOKIES_B64')
YTDLP_PROXY = os.getenv('YTDLP_PROXY')

# Invidious/Piped instances (comma-separated in env), with defaults
_inv_raw = os.getenv('INVIDIOUS_INSTANCES', '').strip()
if _inv_raw:
    INVIDIOUS_INSTANCES = [x.strip() for x in _inv_raw.split(',') if x.strip()]
else:
    INVIDIOUS_INSTANCES = [
        'https://yewtu.be',
        'https://inv.tux.pizza',
        'https://invidious.privacydev.net',
        'https://vid.puffyan.us',
    ]

_piped_raw = os.getenv('PIPED_INSTANCES', '').strip()
if _piped_raw:
    PIPED_INSTANCES = [x.strip() for x in _piped_raw.split(',') if x.strip()]
else:
    PIPED_INSTANCES = [
        'https://piped.video',
        'https://piped.mha.fi',
        'https://piped.tokhmi.xyz',
    ]
