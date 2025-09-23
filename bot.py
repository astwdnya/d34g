import os
import asyncio
import aiohttp
import tempfile
import time
from urllib.parse import urlparse
from pathlib import Path
from uuid import uuid4
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.request import HTTPXRequest
from telegram.error import Conflict, BadRequest, Forbidden
from config import (
    BOT_TOKEN,
    BOT_API_BASE_URL,
    BOT_API_BASE_FILE_URL,
    TG_SESSION_STRING,
    BRIDGE_CHANNEL_ID,
    AUTHORIZED_USERS as CFG_AUTH_USERS,
    ALLOW_ALL,
)
try:
    from uploader import upload_to_bridge
except Exception:
    upload_to_bridge = None

class TelegramDownloadBot:
    def __init__(self):
        # Build Application with optional Local Bot API server
        builder = Application.builder().token(BOT_TOKEN)
        if BOT_API_BASE_URL:
            # Point to local Bot API server to lift 50MB cloud limit (up to 2GB)
            builder = builder.base_url(BOT_API_BASE_URL)
            if BOT_API_BASE_FILE_URL:
                builder = builder.base_file_url(BOT_API_BASE_FILE_URL)
            # Increase timeouts for large media uploads
            req = HTTPXRequest(
                read_timeout=None,
                write_timeout=None,
                connect_timeout=30.0,
                pool_timeout=30.0,
                media_write_timeout=None,
            )
            builder = builder.request(req).get_updates_request(req)
            print(f"🔗 Using Local Bot API server: {BOT_API_BASE_URL}")

        # Define a post_init hook to run after application initialization
        async def _post_init(app):
            try:
                await app.bot.delete_webhook(drop_pending_updates=True)
                print("🔧 Webhook removed (if existed); polling enabled.")
            except Exception as e:
                print(f"⚠️ Could not delete webhook: {e}")
            try:
                me = await app.bot.get_me()
                print(f"✅ Connected as @{me.username} (ID: {me.id})")
                if BOT_API_BASE_URL:
                    print(f"➡️ Using Bot API server: {BOT_API_BASE_URL}")
                else:
                    print("➡️ Using Telegram Cloud Bot API")
                if self.allow_all:
                    print("🔓 ALLOW_ALL is enabled (temporary). All users can use the bot.")
                else:
                    print(f"👤 Authorized users: {sorted(self.authorized_users)}")
            except Exception as e:
                print(f"⚠️ getMe failed: {e}")

        builder = builder.post_init(_post_init)
        self.app = builder.build()
        # Authorized user IDs
        default_users = {818185073, 6936101187, 7972834913}
        self.authorized_users = set(CFG_AUTH_USERS) if CFG_AUTH_USERS else default_users
        self.allow_all = bool(ALLOW_ALL)
        # token -> {file_path, filename, file_size, user_id, user_name, chat_id, progress_msg, update, job}
        self.pending_videos = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup command and message handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("id", self.id_command))
        # Callback handler for post-download video options
        self.app.add_handler(CallbackQueryHandler(self.on_video_option, pattern=r"^videoopt:"))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_link))
        # Centralized error handler (e.g., for 409 Conflict)
        self.app.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log errors globally to avoid noisy tracebacks and explain common cases."""
        err = context.error
        if isinstance(err, Conflict) or (err and "Conflict" in str(err)):
            print("⚠️ Conflict: Another getUpdates request is running. Ensure only one bot instance is polling.")
            return
        print(f"⚠️ Unhandled error: {err}")
    
    def is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        if self.allow_all:
            return True
        return user_id in self.authorized_users
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        print(f"📱 /start command received from user: {user.first_name} (@{user.username}) - ID: {user.id}")
        
        # Check if user is authorized - silently ignore if not
        if not self.is_authorized_user(user.id):
            print(f"🚫 Unauthorized access attempt by {user.first_name} (ID: {user.id})")
            await update.message.reply_text(
                f"🚫 دسترسی شما مجاز نیست.\nشناسه شما: {user.id}\nاز ادمین بخواهید شما را به لیست مجاز اضافه کند یا موقتاً ALLOW_ALL را فعال کند."
            )
            return
        
        welcome_message = """
🤖 سلام! من ربات دانلود فایل هستم

لینک مستقیم دانلود فایل خودتون رو برام بفرستید تا فایل رو براتون دانلود کنم و ارسال کنم.

برای راهنمایی /help رو بزنید.
        """
        await update.message.reply_text(welcome_message)
        print(f"✅ Welcome message sent to {user.first_name}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user = update.effective_user
        print(f"❓ /help command received from user: {user.first_name} (@{user.username}) - ID: {user.id}")
        
        # Check if user is authorized - silently ignore if not
        if not self.is_authorized_user(user.id):
            print(f"🚫 Unauthorized help request by {user.first_name} (ID: {user.id}) - ignored")
            return
        
        help_message = """
📖 راهنمای استفاده:

1️⃣ لینک مستقیم دانلود فایل رو برام بفرست
2️⃣ من فایل رو دانلود می‌کنم
3️⃣ فایل رو مستقیماً براتون ارسال می‌کنم

⚠️ نکات مهم:
• لینک باید مستقیم باشه (نه لینک صفحه)
• بدون محدودیت حجم فایل
• فرمت‌های پشتیبانی شده: تمام فرمت‌ها

مثال لینک معتبر:
https://example.com/file.pdf
https://example.com/image.jpg
        """
        await update.message.reply_text(help_message)
        print(f"✅ Help message sent to {user.first_name}")
    
    async def id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return user's Telegram ID for whitelisting"""
        user = update.effective_user
        await update.message.reply_text(f"🆔 شناسه کاربری شما: {user.id}")
        print(f"ℹ️ /id requested by {user.first_name} - ID: {user.id}")

    async def handle_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle download links sent by users"""
        user = update.effective_user
        url = update.message.text.strip()
        
        print(f"🔗 Download request received from {user.first_name} (@{user.username}) - ID: {user.id}")
        print(f"📎 Requested URL: {url}")
        
        # Check if user is authorized - silently ignore if not
        if not self.is_authorized_user(user.id):
            print(f"🚫 Unauthorized download request by {user.first_name} (ID: {user.id})")
            await update.message.reply_text(
                f"🚫 دسترسی شما مجاز نیست.\nشناسه شما: {user.id}\nاز ادمین بخواهید شما را به لیست مجاز اضافه کند یا موقتاً ALLOW_ALL را فعال کند."
            )
            return
        
        # Check if the message contains a valid URL
        if not self.is_valid_url(url):
            print(f"❌ Invalid URL provided by {user.first_name}")
            await update.message.reply_text("❌ لینک نامعتبر است! لطفاً یک لینک مستقیم دانلود ارسال کنید.")
            return
        
        # Send processing message
        print(f"⏳ Starting download process for {user.first_name}")
        processing_msg = await update.message.reply_text("⏳ در حال دانلود فایل...")
        
        try:
            # Download the file with progress
            print(f"📥 Downloading file from: {url}")
            file_path, filename, file_size = await self.download_file(url, processing_msg, user.first_name)
            print(f"✅ File downloaded successfully: {filename} ({self.format_file_size(file_size)})")
            
            # If it's a video, offer options before upload (valid for 1 hour)
            if self.is_video_file(filename):
                await self.offer_video_options(update, context, processing_msg, file_path, filename, file_size, user.first_name)
                return
            
            # Otherwise, upload immediately
            print(f"📤 Uploading file to Telegram for {user.first_name}")
            await self.upload_with_progress(update, context, processing_msg, file_path, filename, file_size, user.first_name)
            print(f"✅ File successfully sent to {user.first_name}: {filename}")
            try:
                await processing_msg.delete()
            except:
                pass
            # Schedule cleanup
            print(f"🗑️ Scheduled file cleanup in 20 seconds: {filename}")
            asyncio.create_task(self.delayed_file_cleanup(file_path, 20))
            
        except Exception as e:
            print(f"❌ Error processing request from {user.first_name}: {str(e)}")
            await processing_msg.edit_text(f"❌ خطا در دانلود فایل: {str(e)}")
    
    def is_valid_url(self, url: str) -> bool:
        """Check if the provided string is a valid URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    async def download_file(self, url: str, progress_msg=None, user_name: str = "") -> tuple:
        """Download file from URL with progress tracking"""
        # Configure session with no size limits
        timeout = aiohttp.ClientTimeout(total=None, connect=30)
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=0)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: نمی‌توان فایل را دانلود کرد")
                
                # Get filename and total size
                filename = self.get_filename_from_response(response, url)
                total_size = int(response.headers.get('content-length', 0))
                
                # Create temporary file
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, filename)
                
                # Download with progress tracking - no size limits
                downloaded = 0
                start_time = time.time()
                last_update = 0
                
                with open(file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks for large files
                        file.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update >= 0.5 and progress_msg and total_size > 0:
                            elapsed_time = current_time - start_time
                            speed = downloaded / elapsed_time if elapsed_time > 0 else 0
                            percentage = (downloaded / total_size) * 100
                            
                            progress_text = self.create_progress_text(
                                "📥 دانلود", percentage, speed, downloaded, total_size
                            )
                            
                            try:
                                await progress_msg.edit_text(progress_text)
                                last_update = current_time
                                print(f"📊 Download progress for {user_name}: {percentage:.1f}% - {self.format_speed(speed)}")
                            except:
                                pass  # Ignore edit errors
                
                return file_path, filename, downloaded
    
    def get_filename_from_response(self, response, url: str) -> str:
        """Extract filename from response headers or URL"""
        # Try to get filename from Content-Disposition header
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            import re
            filename_match = re.findall('filename="(.+)"', content_disposition)
            if filename_match:
                return filename_match[0]
        
        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        # If no filename found, use a default name
        if not filename or '.' not in filename:
            filename = "downloaded_file"
        
        return filename
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def is_video_file(self, filename: str) -> bool:
        """Check if file is a video based on extension"""
        video_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
            '.m4v', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
        }
        return any(filename.lower().endswith(ext) for ext in video_extensions)
    
    def is_audio_file(self, filename: str) -> bool:
        """Check if file is audio based on extension"""
        audio_extensions = {
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', 
            '.opus', '.aiff', '.au', '.ra'
        }
        return any(filename.lower().endswith(ext) for ext in audio_extensions)
    
    def is_photo_file(self, filename: str) -> bool:
        """Check if file is a photo based on extension"""
        photo_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', 
            '.tiff', '.tif', '.svg', '.ico'
        }
        return any(filename.lower().endswith(ext) for ext in photo_extensions)
    
    def create_progress_text(self, action: str, percentage: float, speed: float, current: int, total: int) -> str:
        """Create progress text with bar and stats"""
        # Create progress bar
        bar_length = 20
        filled_length = int(bar_length * percentage / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        # Format text
        speed_text = self.format_speed(speed)
        current_size = self.format_file_size(current)
        total_size = self.format_file_size(total)
        
        return f"""{action} در حال انجام...

{bar} {percentage:.1f}%

📊 حجم: {current_size} / {total_size}
🚀 سرعت: {speed_text}

لطفاً صبر کنید..."""
    
    def format_speed(self, bytes_per_second: float) -> str:
        """Format speed in human readable format"""
        if bytes_per_second == 0:
            return "0 B/s"
        
        speed_names = ["B/s", "KB/s", "MB/s", "GB/s"]
        import math
        i = int(math.floor(math.log(bytes_per_second, 1024)))
        if i >= len(speed_names):
            i = len(speed_names) - 1
        p = math.pow(1024, i)
        s = round(bytes_per_second / p, 1)
        return f"{s} {speed_names[i]}"
    
    async def upload_with_progress(self, update, context, progress_msg, file_path: str, filename: str, file_size: int, user_name: str):
        """Upload file with progress tracking"""
        start_time = time.time()
        
        # Show initial upload message
        progress_text = self.create_progress_text("📤 آپلود", 0, 0, 0, file_size)
        await progress_msg.edit_text(progress_text)
        
        # If Local Bot API not configured and file > 50MB and bridge is configured, use user-account bridge
        bridge_configured = bool(TG_SESSION_STRING) and BRIDGE_CHANNEL_ID != 0 and upload_to_bridge is not None
        if not BOT_API_BASE_URL and file_size > 50 * 1024 * 1024 and bridge_configured:
            try:
                await progress_msg.edit_text("🚀 در حال ارسال از طریق حساب کاربری (بدون محدودیت 50MB)...")
            except:
                pass
            try:
                caption = f"✅ فایل آپلود شد (Bridge)\n📁 {filename}\n📊 {self.format_file_size(file_size)}"
                bridge_chat_id, message_id = await upload_to_bridge(file_path, filename, caption)
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=bridge_chat_id,
                    message_id=message_id
                )
                try:
                    await progress_msg.delete()
                except:
                    pass
                return
            except (BadRequest, Forbidden) as e:
                await update.message.reply_text(
                    "⚠️ دسترسی ربات به کانال Bridge مشکل دارد. ربات را ادمین کانال خصوصی قرار دهید و دوباره تلاش کنید."
                )
                raise e
            except Exception as e:
                await update.message.reply_text(
                    f"⚠️ ارسال از طریق Bridge با خطا مواجه شد: {e}\nتلاش برای ارسال مستقیم از طریق Bot API..."
                )
                # continue to direct upload fallback

        # Note: To avoid truncated uploads, we stream the real file handle via InputFile
        # and let HTTPX handle chunking. This prevents calling read(-1) on a wrapper.
        
        # Upload the file based on its type with fallback for large files
        caption = f"✅ فایل با موفقیت دانلود شد!\n📁 نام فایل: {filename}\n📊 حجم: {self.format_file_size(file_size)}"
        try:
            with open(file_path, 'rb') as file:
                media_file = InputFile(file, filename=filename, read_file_handle=False)
                if self.is_video_file(filename):
                    await update.message.reply_video(
                        video=media_file,
                        caption=caption,
                        supports_streaming=True
                    )
                elif self.is_audio_file(filename):
                    await update.message.reply_audio(
                        audio=media_file,
                        caption=caption
                    )
                elif self.is_photo_file(filename):
                    await update.message.reply_photo(
                        photo=media_file,
                        caption=caption
                    )
                else:
                    await update.message.reply_document(
                        document=media_file,
                        caption=caption
                    )
        except Exception as e:
            # If sending as media fails (413 error), fallback to document
            if "413" in str(e) or "Request Entity Too Large" in str(e):
                print(f"⚠️ Media upload failed due to size limit, falling back to document: {filename}")
                try:
                    with open(file_path, 'rb') as file:
                        await update.message.reply_document(
                            document=InputFile(file, filename=filename, read_file_handle=False),
                            caption=f"📄 فایل به صورت سند ارسال شد (حجم بزرگ)\n📁 نام فایل: {filename}\n📊 حجم: {self.format_file_size(file_size)}"
                        )
                except Exception as e2:
                    if "413" in str(e2) or "Request Entity Too Large" in str(e2):
                        if not BOT_API_BASE_URL:
                            await update.message.reply_text(
                                "⚠️ محدودیت 50MB در Bot API ابری. برای ارسال فایل‌های بزرگ (تا 2GB) باید Local Bot API Server را راه‌اندازی کنید و متغیرهای BOT_API_BASE_URL و BOT_API_BASE_FILE_URL را تنظیم کنید."
                            )
                        else:
                            await update.message.reply_text(
                                "⚠️ ارسال فایل در حالت Local Bot API هم ناموفق بود. لطفاً پیکربندی سرور Local Bot API را بررسی کنید."
                            )
                    else:
                        raise e2
            else:
                raise e
    


    async def delayed_file_cleanup(self, file_path: str, delay_seconds: int):
        """Delete file after specified delay"""
        try:
            await asyncio.sleep(delay_seconds)
            if os.path.exists(file_path):
                os.unlink(file_path)
                print(f"File deleted after {delay_seconds} seconds: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")
    
    def run(self):
        """Start the bot"""
        print("🤖 Bot started successfully!")
        print("📊 Bot is now online and waiting for requests...")
        print("=" * 50)
        self.app.run_polling(drop_pending_updates=True)

    # ===================== New: Video post-download options =====================
    async def offer_video_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE, processing_msg, file_path: str, filename: str, file_size: int, user_name: str):
        """Offer user to choose how to send the downloaded video: cancel, original, or 16:9.
        Gives the user up to 60 minutes to choose. If no choice is made, defaults to Original.
        """
        token = uuid4().hex
        keyboard = [
            [
                InlineKeyboardButton("❌ لغو و حذف", callback_data=f"videoopt:cancel:{token}"),
                InlineKeyboardButton("🗂️ ارجینال", callback_data=f"videoopt:orig:{token}"),
                InlineKeyboardButton("📺 16:9", callback_data=f"videoopt:169:{token}"),
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        try:
            await processing_msg.edit_text(
                "✅ ویدیو دانلود شد.\n\nتا ۶۰ دقیقه فرصت دارید یکی از گزینه‌ها را انتخاب کنید:",
                reply_markup=markup
            )
        except Exception:
            pass

        # Schedule timeout (60 minutes) if JobQueue is available
        job = None
        if getattr(context, "job_queue", None):
            job = context.job_queue.run_once(self.video_choice_timeout, when=60*60, data=token)
        else:
            print("⚠️ JobQueue not available. Install python-telegram-bot[job-queue] to enable auto-timeout. Buttons will stay active without timeout.")
        self.pending_videos[token] = {
            "file_path": file_path,
            "filename": filename,
            "file_size": file_size,
            "user_id": update.effective_user.id,
            "user_name": user_name,
            "chat_id": update.effective_chat.id,
            "progress_msg": processing_msg,
            "update": update,
            "job": job,
        }
        print(f"⏳ Waiting for user choice (up to 60 min): {filename} | token={token}")

    async def on_video_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button selection for video options."""
        query = update.callback_query
        data = query.data  # e.g., videoopt:orig:<token>
        await query.answer()
        try:
            _, action, token = data.split(":", 2)
        except ValueError:
            return
        meta = self.pending_videos.get(token)
        if not meta:
            # Already handled or expired
            try:
                await query.edit_message_text("⏱️ مهلت انتخاب به پایان رسید یا قبلاً پردازش شده است.")
            except Exception:
                pass
            return

        # Only the original requester can interact
        if update.effective_user.id != meta["user_id"]:
            await query.answer("این گزینه مربوط به فایل شما نیست.", show_alert=True)
            return

        # Consume and cancel timeout once a valid user acts
        self.pending_videos.pop(token, None)
        try:
            meta["job"].schedule_removal()
        except Exception:
            pass

        file_path = meta["file_path"]
        filename = meta["filename"]
        file_size = meta["file_size"]
        progress_msg = meta["progress_msg"]
        orig_update = meta["update"]
        user_name = meta["user_name"]

        # Remove buttons to avoid double taps
        try:
            await context.bot.edit_message_reply_markup(chat_id=meta["chat_id"], message_id=progress_msg.message_id, reply_markup=None)
        except Exception:
            pass

        if action == "cancel":
            # Delete file and inform user
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass
            try:
                await progress_msg.edit_text("❌ عملیات لغو شد و فایل از سرور حذف شد.")
            except Exception:
                pass
            print(f"🗑️ User canceled and file deleted: {filename}")
            return

        if action == "orig":
            try:
                await progress_msg.edit_text("📤 در حال آپلود با سایز اصلی …")
            except Exception:
                pass
            await self.upload_with_progress(orig_update, context, progress_msg, file_path, filename, file_size, user_name)
            try:
                await progress_msg.delete()
            except Exception:
                pass
            asyncio.create_task(self.delayed_file_cleanup(file_path, 20))
            print(f"✅ Original video sent: {filename}")
            return

        if action == "169":
            try:
                await progress_msg.edit_text("🎞️ در حال تبدیل ویدیو به نسبت 16:9 … ممکن است چند دقیقه طول بکشد…")
            except Exception:
                pass
            try:
                out_path, out_name, out_size = await self.ffmpeg_convert_to_16_9(file_path, filename)
            except Exception as e:
                print(f"❌ FFmpeg error: {e}")
                try:
                    await progress_msg.edit_text(f"❌ خطا در تبدیل ویدیو: {e}\nارسال نسخه اصلی…")
                except Exception:
                    pass
                # Fallback to original
                await self.upload_with_progress(orig_update, context, progress_msg, file_path, filename, file_size, user_name)
                try:
                    await progress_msg.delete()
                except Exception:
                    pass
                asyncio.create_task(self.delayed_file_cleanup(file_path, 20))
                return

            # Upload converted
            try:
                await progress_msg.edit_text("📤 در حال آپلود نسخه 16:9 …")
            except Exception:
                pass
            await self.upload_with_progress(orig_update, context, progress_msg, out_path, out_name, out_size, user_name)
            try:
                await progress_msg.delete()
            except Exception:
                pass
            # Schedule cleanup for both files
            asyncio.create_task(self.delayed_file_cleanup(file_path, 20))
            asyncio.create_task(self.delayed_file_cleanup(out_path, 20))
            print(f"✅ 16:9 video sent: {out_name}")
            return

    async def video_choice_timeout(self, context: ContextTypes.DEFAULT_TYPE):
        """Called when user didn't choose within 60 minutes: default to Original upload."""
        token = context.job.data
        meta = self.pending_videos.pop(token, None)
        if not meta:
            return
        file_path = meta["file_path"]
        filename = meta["filename"]
        file_size = meta["file_size"]
        progress_msg = meta["progress_msg"]
        orig_update = meta["update"]
        user_name = meta["user_name"]
        try:
            await progress_msg.edit_text("⌛ مهلت انتخاب به پایان رسید. ارسال با سایز اصلی…")
        except Exception:
            pass
        await self.upload_with_progress(orig_update, context, progress_msg, file_path, filename, file_size, user_name)
        try:
            await progress_msg.delete()
        except Exception:
            pass
        asyncio.create_task(self.delayed_file_cleanup(file_path, 20))

    async def ffmpeg_convert_to_16_9(self, src_path: str, filename: str) -> tuple:
        """Convert video to 16:9 letterboxed 720p using ffmpeg. Returns (out_path, out_name, out_size)."""
        base, _ = os.path.splitext(os.path.basename(filename))
        out_name = f"{base}_16x9.mp4"
        out_path = os.path.join(tempfile.gettempdir(), out_name)
        # Scale to fit within 1280x720 preserving AR, then pad to exactly 1280x720
        vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"
        cmd = [
            "ffmpeg", "-y", "-i", src_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            out_path,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(err.decode(errors='ignore')[-400:])
        out_size = os.path.getsize(out_path)
        return out_path, out_name, out_size

if __name__ == "__main__":
    bot = TelegramDownloadBot()
    bot.run()
