import os
import asyncio
import aiohttp
import tempfile
from urllib.parse import urlparse
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN

class TelegramDownloadBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        # Authorized user IDs
        self.authorized_users = {818185073, 6936101187}
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
• حداکثر حجم فایل: 2 گیگابایت
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
            # Download the file
            print(f"📥 Downloading file from: {url}")
            file_path, filename, file_size = await self.download_file(url)
            print(f"✅ File downloaded successfully: {filename} ({self.format_file_size(file_size)})")
            
            # Check file size (Updated limit to 2GB)
            if file_size > 2 * 1024 * 1024 * 1024:  # 2GB in bytes
                print(f"❌ File too large ({self.format_file_size(file_size)}) - rejected")
                await processing_msg.edit_text("❌ حجم فایل بیش از 2 گیگابایت است!")
                os.unlink(file_path)  # Delete the downloaded file
                return
            
            # Update message
            await processing_msg.edit_text("📤 در حال ارسال فایل...")
            print(f"📤 Uploading file to Telegram for {user.first_name}")
            
            # Send the file
            with open(file_path, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    filename=filename,
                    caption=f"✅ فایل با موفقیت دانلود شد!\n📁 نام فایل: {filename}\n📊 حجم: {self.format_file_size(file_size)}"
                )
            
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
    
    async def download_file(self, url: str) -> tuple:
        """Download file from URL and return file path, filename, and size"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: نمی‌توان فایل را دانلود کرد")
                
                # Get filename from URL or Content-Disposition header
                filename = self.get_filename_from_response(response, url)
                
                # Create temporary file
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, filename)
                
                # Download file
                total_size = 0
                with open(file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        file.write(chunk)
                        total_size += len(chunk)
                
                return file_path, filename, total_size
    
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
