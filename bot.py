import os
import asyncio
import aiohttp
import tempfile
import time
from urllib.parse import urlparse
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN

class TelegramDownloadBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        # Authorized user IDs
        self.authorized_users = {818185073, 6936101187, 7972834913}
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup command and message handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_link))
    
    def is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        return user_id in self.authorized_users
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        print(f"📱 /start command received from user: {user.first_name} (@{user.username}) - ID: {user.id}")
        
        # Check if user is authorized - silently ignore if not
        if not self.is_authorized_user(user.id):
            print(f"🚫 Unauthorized access attempt by {user.first_name} (ID: {user.id}) - ignored")
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
    
    async def handle_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle download links sent by users"""
        user = update.effective_user
        url = update.message.text.strip()
        
        print(f"🔗 Download request received from {user.first_name} (@{user.username}) - ID: {user.id}")
        print(f"📎 Requested URL: {url}")
        
        # Check if user is authorized - silently ignore if not
        if not self.is_authorized_user(user.id):
            print(f"🚫 Unauthorized download request by {user.first_name} (ID: {user.id}) - ignored")
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
            
            # No file size limit - removed all restrictions
            
            # Upload with progress tracking - detect file type
            print(f"📤 Uploading file to Telegram for {user.first_name}")
            await self.upload_with_progress(update, processing_msg, file_path, filename, file_size, user.first_name)
            
            print(f"✅ File successfully sent to {user.first_name}: {filename}")
            
            # Delete processing message
            await processing_msg.delete()
            
            # Schedule file deletion after 20 seconds
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
                        
                        # Update progress every 2 seconds
                        current_time = time.time()
                        if current_time - last_update >= 2 and progress_msg and total_size > 0:
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
    
    async def upload_with_progress(self, update, progress_msg, file_path: str, filename: str, file_size: int, user_name: str):
        """Upload file with progress tracking"""
        start_time = time.time()
        
        # Show initial upload message
        progress_text = self.create_progress_text("📤 آپلود", 0, 0, 0, file_size)
        await progress_msg.edit_text(progress_text)
        
        # Create a custom progress callback
        uploaded = 0
        last_update = 0
        
        class ProgressFile:
            def __init__(self, file_obj, total_size, callback):
                self.file_obj = file_obj
                self.total_size = total_size
                self.callback = callback
                self.uploaded = 0
                
            def read(self, size=-1):
                data = self.file_obj.read(size)
                if data:
                    self.uploaded += len(data)
                    asyncio.create_task(self.callback(self.uploaded, self.total_size))
                return data
                
            def __getattr__(self, name):
                return getattr(self.file_obj, name)
        
        async def progress_callback(current, total):
            nonlocal last_update
            current_time = time.time()
            
            if current_time - last_update >= 1:  # Update every second for upload
                elapsed_time = current_time - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                percentage = (current / total) * 100 if total > 0 else 0
                
                progress_text = self.create_progress_text(
                    "📤 آپلود", percentage, speed, current, total
                )
                
                try:
                    await progress_msg.edit_text(progress_text)
                    last_update = current_time
                    print(f"📊 Upload progress for {user_name}: {percentage:.1f}% - {self.format_speed(speed)}")
                except:
                    pass
        
        # Upload the file based on its type with fallback for large files
        with open(file_path, 'rb') as file:
            progress_file = ProgressFile(file, file_size, progress_callback)
            caption = f"✅ فایل با موفقیت دانلود شد!\n📁 نام فایل: {filename}\n📊 حجم: {self.format_file_size(file_size)}"
            
            try:
                if self.is_video_file(filename):
                    # Try to send as video first
                    await update.message.reply_video(
                        video=progress_file,
                        caption=caption,
                        supports_streaming=True
                    )
                elif self.is_audio_file(filename):
                    # Try to send as audio first
                    await update.message.reply_audio(
                        audio=progress_file,
                        caption=caption
                    )
                elif self.is_photo_file(filename):
                    # Try to send as photo first
                    await update.message.reply_photo(
                        photo=progress_file,
                        caption=caption
                    )
                else:
                    # Send as document for other file types
                    await update.message.reply_document(
                        document=progress_file,
                        filename=filename,
                        caption=caption
                    )
            except Exception as e:
                # If sending as media fails (413 error), fallback to document
                if "413" in str(e) or "Request Entity Too Large" in str(e):
                    print(f"⚠️ Media upload failed due to size limit, falling back to document: {filename}")
                    # Reset file pointer and send as document
                    file.seek(0)
                    progress_file = ProgressFile(file, file_size, progress_callback)
                    await update.message.reply_document(
                        document=progress_file,
                        filename=filename,
                        caption=f"📄 فایل به صورت سند ارسال شد (حجم بزرگ)\n📁 نام فایل: {filename}\n📊 حجم: {self.format_file_size(file_size)}"
                    )
                else:
                    # Re-raise other exceptions
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

if __name__ == "__main__":
    bot = TelegramDownloadBot()
    bot.run()
