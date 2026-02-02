#!/usr/bin/env python3
"""
Telegram bot base class for Kalshibot
"""

import os
import json
import requests
from datetime import datetime, timezone

class TelegramBot:
    def __init__(self):
        self.bot_token = "7790219276:AAHGWxUY9NqKvUuKNIrIkrmr3-YPG7L7JsY"
        self.chat_id = "213332819"
        self.sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
        self.credentials_path = "/home/ubuntu/google_credentials.json"
    
    def send_telegram_message(self, message):
        """Send message via Telegram bot"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            print(f"✅ Telegram message sent successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending Telegram message: {e}")
            return False
    
    def get_alert_count(self):
        """Get total number of alerts logged"""
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            service = build('sheets', 'v4', credentials=credentials)
            
            result = service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Alerts!A:A'
            ).execute()
            
            values = result.get('values', [])
            return max(0, len(values) - 1)  # Subtract header row
            
        except Exception as error:
            print(f"❌ Error getting alert count: {error}")
            return 0
