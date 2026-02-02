#!/usr/bin/env python3
"""
Improved Two-way Telegram bot for Kalshibot command execution with enhanced logging
"""

import os
import json
import time
import requests
import subprocess
import logging
from datetime import datetime, timezone
from telegram_bot import TelegramBot

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/kalshibot/telegram_bot_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ImprovedTelegramCommandBot(TelegramBot):
    def __init__(self):
        super().__init__()
        self.last_update_id = 0
        self.commands = {
            'run kalshi sync': self.run_kalshi_sync,
            'kalshi sync': self.run_kalshi_sync,
            'check our x feed': self.check_x_feed,
            'check x feed': self.check_x_feed,
            'status': self.get_status,
            'help': self.show_help,
            'debug': self.debug_info,
        }
        logger.info("🤖 Telegram Command Bot initialized")
    
    def get_updates(self):
        """Get updates from Telegram bot API with improved error handling"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 10
            }
            
            logger.debug(f"📡 Polling Telegram API with offset: {self.last_update_id + 1}")
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data['ok']:
                updates = data['result']
                logger.debug(f"📨 Received {len(updates)} updates")
                return updates
            else:
                logger.error(f"❌ Telegram API error: {data}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get Telegram updates: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error getting updates: {e}")
            return []
    
    def process_message(self, message):
        """Process incoming message with enhanced logging"""
        try:
            # Extract message details
            chat_id = str(message['chat']['id'])
            user_id = str(message['from']['id'])
            text = message.get('text', '').lower().strip()
            message_id = message.get('message_id', 'unknown')
            
            logger.info(f"📨 [MSG {message_id}] Received from user {user_id}: '{text}'")
            
            # Only respond to messages from the authorized user
            if user_id != self.chat_id:
                logger.warning(f"⚠️  [MSG {message_id}] Ignoring message from unauthorized user: {user_id}")
                return
            
            # Find matching command
            command_found = False
            for cmd_key, cmd_func in self.commands.items():
                if cmd_key in text:
                    logger.info(f"🎯 [MSG {message_id}] Executing command: {cmd_key}")
                    try:
                        cmd_func()
                        logger.info(f"✅ [MSG {message_id}] Command '{cmd_key}' completed successfully")
                    except Exception as cmd_error:
                        logger.error(f"❌ [MSG {message_id}] Command '{cmd_key}' failed: {cmd_error}")
                        self.send_telegram_message(f"❌ Command failed: {str(cmd_error)}")
                    command_found = True
                    break
            
            if not command_found:
                logger.info(f"❓ [MSG {message_id}] Unknown command: '{text}'")
                self.send_unknown_command_message(text)
                
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            try:
                self.send_telegram_message(f"❌ Error processing command: {str(e)}")
            except:
                logger.error("❌ Failed to send error message to user")
    
    def run_kalshi_sync(self):
        """Execute Kalshi sync command with enhanced logging"""
        logger.info("🔄 Starting Kalshi sync...")
        
        try:
            self.send_telegram_message("🔄 Running Kalshi sync...")
            
            # Execute the Kalshi sync script
            logger.info("📊 Executing kalshi_simple_fetcher.py...")
            result = subprocess.run(
                ['python3', 'kalshi_simple_fetcher.py'],
                cwd='/home/ubuntu/kalshibot',
                capture_output=True,
                text=True,
                timeout=180
            )
            
            logger.info(f"📊 Kalshi sync completed with return code: {result.returncode}")
            
            if result.returncode == 0:
                output = result.stdout
                logger.debug(f"📊 Kalshi sync output: {output[:500]}...")
                
                # Parse output for summary
                if "No contracts match filter criteria" in output:
                    summary = "⚠️ No contracts match filter criteria"
                elif "Filtered to" in output:
                    filtered_lines = [line for line in output.split('\n') if "Filtered to" in line]
                    summary = filtered_lines[0] if filtered_lines else "Kalshi sync completed"
                else:
                    summary = "Kalshi sync completed - check logs for details"
                
                message = f"""✅ **Kalshi Sync Complete**

{summary}

🔗 [View WatchlistContracts](https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8)"""
                
                self.send_telegram_message(message)
                logger.info("✅ Kalshi sync completed successfully")
                
            else:
                error_output = result.stderr[:300] if result.stderr else "Unknown error"
                logger.error(f"❌ Kalshi sync failed: {error_output}")
                self.send_telegram_message(f"❌ **Kalshi Sync Failed**\n\nError: {error_output}")
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ Kalshi sync timed out")
            self.send_telegram_message("⏰ Kalshi sync timed out (3 minute limit)")
        except Exception as e:
            logger.error(f"❌ Error running Kalshi sync: {e}")
            self.send_telegram_message(f"❌ Error running Kalshi sync: {str(e)}")
    
    def check_x_feed(self):
        """Execute X feed check command with enhanced logging"""
        logger.info("🐦 Starting X feed check...")
        
        try:
            self.send_telegram_message("🐦 Checking X feed...")
            
            # Execute the X feed extraction script
            logger.info("📱 Executing extract_tweets.py...")
            result = subprocess.run(
                ['python3', 'extract_tweets.py'],
                cwd='/home/ubuntu/kalshibot',
                capture_output=True,
                text=True,
                timeout=90
            )
            
            logger.info(f"📱 X feed check completed with return code: {result.returncode}")
            
            if result.returncode == 0:
                output = result.stdout
                logger.debug(f"📱 X feed output: {output[:500]}...")
                
                # Parse output for summary
                tweets_processed = 0
                alerts_generated = 0
                most_recent_tweet = "No tweets found"
                
                lines = output.split('\n')
                for line in lines:
                    if 'tweets processed' in line and 'alerts generated' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'processed:' and i+1 < len(parts):
                                tweets_processed = parts[i+1]
                            elif part == 'generated:' and i+1 < len(parts):
                                alerts_generated = parts[i+1]
                    
                    elif 'Processing tweet from @' in line and most_recent_tweet == "No tweets found":
                        handle = line.split('Processing tweet from ')[1].split(':')[0]
                        for j, next_line in enumerate(lines[lines.index(line):]):
                            if 'Text:' in next_line:
                                tweet_text = next_line.split('Text: ')[1].split('...')[0]
                                most_recent_tweet = f"{handle}: {tweet_text}..."
                                break
                
                message = f"""✅ **X Feed Check Complete**

📊 **Results:**
• Tweets processed: {tweets_processed}
• Alerts generated: {alerts_generated}

🐦 **Most Recent Tweet:**
{most_recent_tweet}

🔗 [View Alerts](https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8) | [View No Action](https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8)"""
                
                self.send_telegram_message(message)
                logger.info("✅ X feed check completed successfully")
                
            else:
                error_output = result.stderr[:300] if result.stderr else "Unknown error"
                logger.error(f"❌ X feed check failed: {error_output}")
                self.send_telegram_message(f"❌ **X Feed Check Failed**\n\nError: {error_output}")
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ X feed check timed out")
            self.send_telegram_message("⏰ X feed check timed out (90s limit)")
        except Exception as e:
            logger.error(f"❌ Error checking X feed: {e}")
            self.send_telegram_message(f"❌ Error checking X feed: {str(e)}")
    
    def debug_info(self):
        """Provide debug information"""
        try:
            # Get system info
            import psutil
            import platform
            
            debug_msg = f"""🔧 **Debug Information**

**System:**
• Platform: {platform.system()} {platform.release()}
• Python: {platform.python_version()}
• Bot PID: {os.getpid()}
• Memory: {psutil.virtual_memory().percent}% used

**Bot Status:**
• Last Update ID: {self.last_update_id}
• Commands: {len(self.commands)}
• Authorized User: {self.chat_id}

**Recent Activity:**
• Log file: telegram_bot_debug.log
• Working directory: /home/ubuntu/kalshibot

**Available Commands:**
{', '.join(self.commands.keys())}"""
            
            self.send_telegram_message(debug_msg)
            logger.info("🔧 Debug info sent to user")
            
        except Exception as e:
            logger.error(f"❌ Error getting debug info: {e}")
            self.send_telegram_message(f"❌ Debug error: {str(e)}")
    
    def get_alert_count(self):
        """Get total number of alerts logged"""
        try:
            from alerts_logger import AlertsLogger
            alerts_logger = AlertsLogger()
            return alerts_logger.get_alert_count()
        except Exception as e:
            logger.error(f"❌ Error getting alert count: {e}")
            return 0
    
    def get_status(self):
        """Get system status with enhanced info"""
        try:
            alert_count = self.get_alert_count()
            
            status_msg = f"""📊 **Kalshibot Status**

🚨 **Total Alerts**: {alert_count}
📈 **Watchlist Contracts**: Active monitoring
🤖 **Bot Status**: Online and responsive
⏰ **Last Check**: {datetime.now(timezone.utc).strftime('%H:%M UTC')}
📝 **Logging**: Enhanced debug mode active

💡 **Available Commands**:
• run kalshi sync
• check our x feed  
• status
• debug
• help"""
            
            self.send_telegram_message(status_msg)
            logger.info("📊 Status sent to user")
            
        except Exception as e:
            logger.error(f"❌ Error getting status: {e}")
            self.send_telegram_message(f"❌ Status error: {str(e)}")
    
    def show_help(self):
        """Show help message"""
        help_msg = """🤖 **Kalshibot Commands**

📈 **Trading Commands**:
• `run kalshi sync` - Update contract watchlist
• `check our x feed` - Process latest tweets

📊 **Status Commands**:
• `status` - System status overview
• `debug` - Debug information
• `help` - Show this help message

💡 Commands are case-insensitive and flexible"""
        
        self.send_telegram_message(help_msg)
        logger.info("❓ Help sent to user")
    
    def send_unknown_command_message(self, text):
        """Send message for unknown commands"""
        message = f"""❓ Unknown command: '{text}'

🤖 **Available Commands:**
• `run kalshi sync` - Update contract watchlist
• `check our x feed` - Process latest tweets
• `status` - System status
• `debug` - Debug info
• `help` - Show help

Commands are case-insensitive."""
        
        self.send_telegram_message(message)
        logger.info(f"❓ Unknown command response sent for: '{text}'")
    
    def start_listening(self):
        """Start listening for Telegram commands with enhanced monitoring"""
        logger.info("🤖 Starting Improved Telegram Command Bot...")
        logger.info(f"👤 Authorized user: {self.chat_id}")
        logger.info("📨 Enhanced logging and error handling active")
        
        # Send startup message
        startup_msg = """🤖 **Kalshibot Command Bot Online** (Enhanced)

**Available Commands:**
• `run kalshi sync` - Update contract watchlist
• `check our x feed` - Process latest tweets
• `status` - System status
• `debug` - Debug information

Enhanced logging and error handling now active."""
        
        try:
            self.send_telegram_message(startup_msg)
            logger.info("📨 Startup message sent")
        except Exception as e:
            logger.error(f"❌ Failed to send startup message: {e}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                updates = self.get_updates()
                
                if updates:
                    consecutive_errors = 0  # Reset error counter on successful update
                    
                for update in updates:
                    self.last_update_id = update['update_id']
                    logger.debug(f"📨 Processing update ID: {self.last_update_id}")
                    
                    if 'message' in update:
                        self.process_message(update['message'])
                
                time.sleep(2)  # Poll every 2 seconds
                
            except KeyboardInterrupt:
                logger.info("\\n🛑 Bot stopped by user")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ Error in main loop (#{consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"💥 Too many consecutive errors ({consecutive_errors}), stopping bot")
                    try:
                        self.send_telegram_message("💥 Bot encountered critical errors and is restarting...")
                    except:
                        pass
                    break
                
                time.sleep(5)  # Wait longer on error

def main():
    """Main function to start the improved command bot"""
    try:
        bot = ImprovedTelegramCommandBot()
        bot.start_listening()
    except Exception as e:
        logger.critical(f"💥 Critical error starting bot: {e}")
        raise

if __name__ == "__main__":
    main()

