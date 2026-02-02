#!/usr/bin/env python3
"""
Two-way Telegram bot for Kalshibot command execution
"""

import os
import json
import time
import requests
import subprocess
from datetime import datetime, timezone
from telegram_bot import TelegramBot

class TelegramCommandBot(TelegramBot):
    def __init__(self):
        super().__init__()
        self.last_update_id = 0
        self.commands = {
            'run kalshi sync': self.run_kalshi_sync,
            'kalshi sync': self.run_kalshi_sync,
            'check our x feed': self.check_x_feed,
            'check x feed': self.check_x_feed,
        }
    
    def get_updates(self):
        """Get updates from Telegram bot API"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 10
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data['ok']:
                return data['result']
            else:
                print(f"❌ Telegram API error: {data}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get Telegram updates: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error getting updates: {e}")
            return []
    
    def process_message(self, message):
        """Process incoming message and execute commands"""
        try:
            # Extract message details
            chat_id = str(message['chat']['id'])
            user_id = str(message['from']['id'])
            text = message.get('text', '').lower().strip()
            
            # Only respond to messages from the authorized user
            if user_id != self.chat_id:
                print(f"⚠️  Ignoring message from unauthorized user: {user_id}")
                return
            
            print(f"📨 Received command: '{text}'")
            
            # Find matching command
            command_found = False
            for cmd_key, cmd_func in self.commands.items():
                if cmd_key in text:
                    print(f"🎯 Executing command: {cmd_key}")
                    cmd_func()
                    command_found = True
                    break
            
            if not command_found:
                self.send_unknown_command_message(text)
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            error_msg = f"❌ Error processing command: {str(e)}"
            self.send_telegram_message(error_msg)
    
    def run_kalshi_sync(self):
        """Execute Kalshi sync command"""
        try:
            self.send_telegram_message("🔄 Running Kalshi sync...")
            
            # Execute the Kalshi sync script with longer timeout
            result = subprocess.run(
                ['python3', 'kalshi_simple_fetcher.py'],
                cwd='/home/ubuntu/kalshibot',
                capture_output=True,
                text=True,
                timeout=180  # Increased to 3 minutes
            )
            
            if result.returncode == 0:
                # Parse output for key information
                output = result.stdout
                
                # Look for key summary lines
                summary_info = []
                if "Filtered to" in output:
                    filtered_line = [line for line in output.split('\n') if "Filtered to" in line]
                    if filtered_line:
                        summary_info.append(filtered_line[0])
                
                if "contracts added" in output or "contracts updated" in output:
                    update_lines = [line for line in output.split('\n') if "contracts added" in line or "contracts updated" in line]
                    summary_info.extend(update_lines)
                
                if "No contracts match filter criteria" in output:
                    summary_info.append("⚠️ No contracts match filter criteria")
                
                # Create summary message
                if summary_info:
                    summary = '\n'.join(summary_info)
                else:
                    summary = "Kalshi sync completed - no changes detected"
                
                message = f"""✅ **Kalshi Sync Complete**

{summary}

🔗 [View WatchlistContracts](https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8)"""
                
                self.send_telegram_message(message)
                
            else:
                error_msg = f"❌ **Kalshi Sync Failed**\n\nError: {result.stderr[:300]}"
                self.send_telegram_message(error_msg)
                
        except subprocess.TimeoutExpired:
            self.send_telegram_message("⏰ Kalshi sync timed out (3 minute limit)")
        except Exception as e:
            self.send_telegram_message(f"❌ Error running Kalshi sync: {str(e)}")
    
    def check_x_feed(self):
        """Execute X feed check command"""
        try:
            self.send_telegram_message("🐦 Checking X feed...")
            
            # Execute the X feed extraction script
            result = subprocess.run(
                ['python3', 'extract_tweets.py'],
                cwd='/home/ubuntu/kalshibot',
                capture_output=True,
                text=True,
                timeout=90
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # Extract summary information
                tweets_processed = 0
                alerts_generated = 0
                most_recent_tweet = "No tweets found"
                
                # Parse output for summary
                lines = output.split('\n')
                for line in lines:
                    if 'tweets processed' in line and 'alerts generated' in line:
                        # Extract numbers from summary line
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'processed:' and i+1 < len(parts):
                                tweets_processed = parts[i+1]
                            elif part == 'generated:' and i+1 < len(parts):
                                alerts_generated = parts[i+1]
                    
                    # Look for first tweet being processed
                    elif 'Processing tweet from @' in line and most_recent_tweet == "No tweets found":
                        # Extract the handle and find the corresponding tweet text
                        handle = line.split('Processing tweet from ')[1].split(':')[0]
                        # Look for the next line with tweet text
                        for j, next_line in enumerate(lines[lines.index(line):]):
                            if 'Text:' in next_line:
                                tweet_text = next_line.split('Text: ')[1].split('...')[0]
                                most_recent_tweet = f"{handle}: {tweet_text}..."
                                break
                
                # Create comprehensive summary
                message = f"""✅ **X Feed Check Complete**

📊 **Results:**
• Tweets processed: {tweets_processed}
• Alerts generated: {alerts_generated}

🐦 **Most Recent Tweet:**
{most_recent_tweet}

🔗 [View Alerts](https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8)"""
                
                self.send_telegram_message(message)
                
            else:
                error_msg = f"❌ **X Feed Check Failed**\n\nError: {result.stderr[:300]}"
                self.send_telegram_message(error_msg)
                
        except subprocess.TimeoutExpired:
            self.send_telegram_message("⏰ X feed check timed out (90s limit)")
        except Exception as e:
            self.send_telegram_message(f"❌ Error checking X feed: {str(e)}")
    
    def get_status(self):
        """Get system status"""
        try:
            # Get alert count
            alert_count = self.get_alert_count()
            
            # Get last sync info (simplified)
            status_msg = f"""📊 **Kalshibot Status**

🚨 **Total Alerts**: {alert_count}
📈 **Watchlist Contracts**: 6 active
🤖 **Bot Status**: Online and monitoring
⏰ **Last Check**: {datetime.now(timezone.utc).strftime('%H:%M UTC')}

💡 **Available Commands**:
• run kalshi sync
• check x feed  
• status
• alerts count
• help"""
            
            self.send_telegram_message(status_msg)
            
        except Exception as e:
            self.send_telegram_message(f"❌ Error getting status: {str(e)}")
    
    def get_alerts_count(self):
        """Get current alerts count"""
        try:
            count = self.get_alert_count()
            message = f"🚨 **Alert Count**: {count} total alerts logged"
            self.send_telegram_message(message)
        except Exception as e:
            self.send_telegram_message(f"❌ Error getting alerts count: {str(e)}")
    
    def send_test_alert(self):
        """Send a test alert"""
        try:
            test_alert = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tweet_id': 'cmd_test_' + str(int(datetime.now().timestamp())),
                'contract_ticker': 'TEST-CONTRACT-2025',
                'sps_score': '0.850',
                'similarity_score': '0.90',
                'sentiment_score': '0.5',
                'certainty_score': '0.95',
                'source_weight': '1.0',
                'username': '@TestUser',
                'tweet_text': 'Test alert triggered via Telegram command. System is working correctly!'
            }
            
            message = self.format_alert_message(test_alert)
            self.send_telegram_message(message)
            
        except Exception as e:
            self.send_telegram_message(f"❌ Error sending test alert: {str(e)}")
    
    def show_help(self):
        """Show help message"""
        help_msg = """🤖 **Kalshibot Commands**

📈 **Trading Commands**:
• `run kalshi sync` - Update contract watchlist
• `check x feed` - Process latest tweets

📊 **Status Commands**:
• `status` - System status overview
• `alerts count` - Total alerts logged

🧪 **Testing**:
• `test alert` - Send test alert
• `help` - Show this help message

💡 Commands are case-insensitive and flexible (e.g., "kalshi sync" also works)"""
        
        self.send_telegram_message(help_msg)
    
    def send_unknown_command_message(self, text):
        """Send message for unknown commands"""
        message = f"""❓ Unknown command: '{text}'

🤖 **Available Commands:**
• `run kalshi sync` - Update contract watchlist
• `check our x feed` - Process latest tweets

Commands are case-insensitive."""
        self.send_telegram_message(message)
    
    def start_listening(self):
        """Start listening for Telegram commands"""
        print("🤖 Starting Telegram command bot...")
        print(f"👤 Authorized user: {self.chat_id}")
        print("📨 Listening for commands...")
        
        # Send startup message
        startup_msg = """🤖 **Kalshibot Command Bot Online**

**Available Commands:**
• `run kalshi sync` - Update contract watchlist
• `check our x feed` - Process latest tweets"""
        self.send_telegram_message(startup_msg)
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    if 'message' in update:
                        self.process_message(update['message'])
                
                time.sleep(2)  # Poll every 2 seconds
                
            except KeyboardInterrupt:
                print("\\n🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(5)  # Wait longer on error

def main():
    """Main function to start the command bot"""
    bot = TelegramCommandBot()
    bot.start_listening()

if __name__ == "__main__":
    main()

