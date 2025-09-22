#!/usr/bin/env python3
"""
Main entry point for Telegram Download Bot
Optimized for Render deployment
"""

import os
import sys
import logging
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

def main():
    """Main function to start the bot"""
    try:
        logger.info("Starting Telegram Download Bot...")
        
        # Import and start the bot
        from bot import TelegramDownloadBot
        
        # Create and run bot instance
        bot = TelegramDownloadBot()
        logger.info("Bot instance created successfully")
        
        # Start the bot
        bot.run()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all dependencies are installed")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
