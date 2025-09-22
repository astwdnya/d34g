#!/usr/bin/env python3
"""
Main entry point for Telegram Download Bot
Optimized for Render deployment with health check server
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add the tgscmr directory to Python path
current_dir = Path(__file__).parent
tgscmr_dir = current_dir / "tgscmr"
sys.path.insert(0, str(tgscmr_dir))

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to start the bot with health server"""
    try:
        logger.info("Starting Telegram Download Bot with Health Server...")
        
        # Start health check server
        from health_server import HealthServer
        health_server = HealthServer(port=int(os.environ.get('PORT', 8080)))
        health_server.start()
        health_server.update_bot_status("initializing")
        
        # Import and start the bot
        from bot import TelegramDownloadBot
        
        # Create bot instance
        bot = TelegramDownloadBot()
        logger.info("Bot instance created successfully")
        health_server.update_bot_status("created")
        
        # Initialize the application
        await bot.app.initialize()
        logger.info("Bot initialized successfully")
        health_server.update_bot_status("initialized")
        
        # Start the bot
        await bot.app.start()
        logger.info("Bot started successfully")
        health_server.update_bot_status("started")
        
        # Start polling
        await bot.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is now polling for updates...")
        health_server.update_bot_status("running")
        
        # Keep the bot running
        await asyncio.Event().wait()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all dependencies are installed")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
