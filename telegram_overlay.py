#!/usr/bin/env python3
"""
Telegram Notification Overlay for Polymarket Stop Loss Bot
This code adds Telegram notifications WITHOUT modifying your existing bot code.

Just import this module in your existing file and it will automatically start
sending Telegram notifications by intercepting your existing log messages.

Usage:
1. Add to your .env file:
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here

2. Add these two lines at the top of your existing file (after imports):
   from telegram_overlay import TelegramOverlay
   TelegramOverlay.initialize()

That's it! No other changes needed.
"""

import logging
import os
import re
import threading
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any

class TelegramHandler(logging.Handler):
    """Custom logging handler that sends specific messages to Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = True
        
        # Test connection
        try:
            self._send_message("🤖 Polymarket Stop Loss Bot - Telegram notifications activated!")
            print("✅ Telegram notifications initialized successfully")
        except Exception as e:
            print(f"⚠️  Telegram initialization failed: {e}")
            self.enabled = False

    def emit(self, record):
        """Handle log records and send relevant ones to Telegram"""
        if not self.enabled:
            return
        
        try:
            message = record.getMessage()
            
            # Parse different types of log messages
            if "STOP LOSS TRIGGERED" in message:
                self._handle_stop_loss_trigger(message)
            elif "STOP LOSS EXECUTED" in message:
                self._handle_stop_loss_execution(message)
            elif "Failed to execute stop loss" in message:
                self._handle_execution_error(message)
            elif "Error in monitoring cycle" in message:
                self._handle_monitoring_error(message)
            elif "Starting Polymarket Stop Loss Bot" in message:
                self._handle_bot_start(message)
            
        except Exception as e:
            print(f"⚠️  Telegram handler error: {e}")

    def _handle_stop_loss_trigger(self, message):
        """Handle stop loss trigger notifications"""
        # Extract details from log message using regex
        # Example: "🚨 STOP LOSS TRIGGERED: Trump wins 2024 (Yes) - Loss: -25.50% ($-127.50)"
        
        pattern = r"🚨 STOP LOSS TRIGGERED: (.+?) \((.+?)\) - Loss: (-?\d+\.?\d*)% \(\$(-?\d+\.?\d*)\)"
        match = re.search(pattern, message)
        
        if match:
            market = match.group(1)
            outcome = match.group(2)
            loss_pct = match.group(3)
            loss_amount = match.group(4)
            
            telegram_message = f"""
🚨 <b>STOP LOSS TRIGGERED</b> 🚨

📊 <b>Market:</b> {market}
🎯 <b>Outcome:</b> {outcome}
📉 <b>Loss:</b> {loss_pct}% (${loss_amount})

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        else:
            # Fallback - send raw message
            telegram_message = f"🚨 <b>STOP LOSS TRIGGERED</b>\n\n{message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self._send_message(telegram_message.strip())

    def _handle_stop_loss_execution(self, message):
        """Handle stop loss execution notifications"""
        # Extract details from execution message
        # Example: "✅ STOP LOSS EXECUTED: Placed 2 orders for Trump wins 2024 (Yes). Target: 100.0, Ordered: 100.0"
        
        pattern = r"✅ STOP LOSS EXECUTED: Placed (\d+) orders for (.+?) \((.+?)\)\. Target: ([\d.]+), Ordered: ([\d.]+)"
        match = re.search(pattern, message)
        
        if match:
            orders_count = match.group(1)
            market = match.group(2)
            outcome = match.group(3)
            target = match.group(4)
            ordered = match.group(5)
            
            telegram_message = f"""
✅ <b>STOP LOSS EXECUTED</b>

📊 <b>Market:</b> {market}
🎯 <b>Outcome:</b> {outcome}
🔄 <b>Orders Placed:</b> {orders_count}
📦 <b>Target Size:</b> {target}
📦 <b>Ordered Size:</b> {ordered}

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        else:
            # Fallback - send raw message
            telegram_message = f"✅ <b>STOP LOSS EXECUTED</b>\n\n{message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self._send_message(telegram_message.strip())

    def _handle_execution_error(self, message):
        """Handle execution error notifications"""
        telegram_message = f"""
❌ <b>EXECUTION ERROR</b>

⚠️ <b>Error:</b> {message}

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self._send_message(telegram_message.strip())

    def _handle_monitoring_error(self, message):
        """Handle monitoring cycle errors"""
        telegram_message = f"""
⚠️ <b>MONITORING ERROR</b>

❌ <b>Details:</b> {message}

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self._send_message(telegram_message.strip())

    def _handle_bot_start(self, message):
        """Handle bot startup notification"""
        telegram_message = f"""
🚀 <b>BOT STARTED</b>

✅ Polymarket Stop Loss Bot is now running
📊 Monitoring for stop loss triggers

⏰ <b>Started:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self._send_message(telegram_message.strip())

    def _send_message(self, message: str):
        """Send message to Telegram (non-blocking)"""
        def send_async():
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                data = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, data=data, timeout=10)
                if not response.ok:
                    print(f"⚠️  Telegram API error: {response.text}")
            except Exception as e:
                print(f"⚠️  Failed to send Telegram message: {e}")
        
        # Send in background thread to avoid blocking
        thread = threading.Thread(target=send_async)
        thread.daemon = True
        thread.start()


class TelegramOverlay:
    """Main overlay class that adds Telegram functionality without code changes"""
    
    _initialized = False
    _handler = None
    
    @classmethod
    def initialize(cls):
        """Initialize Telegram overlay - call this once in your main file"""
        if cls._initialized:
            return
        
        try:
            # Get credentials from environment
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if not bot_token or not chat_id:
                print("⚠️  Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
                print("   Add these to your .env file to enable notifications")
                return
            
            # Create and add the handler to root logger
            cls._handler = TelegramHandler(bot_token, chat_id)
            cls._handler.setLevel(logging.INFO)
            
            # Add to root logger to catch all log messages
            root_logger = logging.getLogger()
            root_logger.addHandler(cls._handler)
            
            cls._initialized = True
            
        except Exception as e:
            print(f"❌ Failed to initialize Telegram overlay: {e}")

    @classmethod
    def send_custom_message(cls, message: str):
        """Send a custom message (useful for testing)"""
        if cls._handler and cls._handler.enabled:
            cls._handler._send_message(message)
        else:
            print("⚠️  Telegram not initialized or disabled")

    @classmethod
    def send_status_update(cls, monitored_count: int, total_count: int, total_value: float):
        """Send a status update"""
        message = f"""
📊 <b>Portfolio Status Update</b>

🎯 <b>Monitored Positions:</b> {monitored_count}
📈 <b>Total Positions:</b> {total_count}
💰 <b>Total Value:</b> ${total_value:.2f}

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        cls.send_custom_message(message.strip())


# Auto-initialization when module is imported (optional)
# Uncomment this if you want automatic initialization
# TelegramOverlay.initialize()


# =============================================================================
# USAGE EXAMPLE - ADD TO YOUR EXISTING FILE
# =============================================================================
"""
STEP 1: Save this code as 'telegram_overlay.py' in the same directory as your bot

STEP 2: Add these lines to the TOP of your existing polymarket bot file (after imports):

    from telegram_overlay import TelegramOverlay
    TelegramOverlay.initialize()

STEP 3: Add to your .env file:
    TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
    TELEGRAM_CHAT_ID=123456789

STEP 4: Install required package:
    pip install requests

That's it! Your bot will now send Telegram notifications with ZERO changes to existing code.

OPTIONAL: For manual status updates, you can add this anywhere in your code:
    TelegramOverlay.send_status_update(monitored_count, total_count, total_value)

TESTING: Send a test message:
    TelegramOverlay.send_custom_message("🧪 Test notification from bot!")
"""
