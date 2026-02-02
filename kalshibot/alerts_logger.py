#!/usr/bin/env python3
"""
Google Sheets alert logger for Kalshibot
"""

import os
import json
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class AlertsLogger:
    def __init__(self):
        self.sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
        self.credentials_path = "/home/ubuntu/google_credentials.json"
        self.service = None
        self._setup_service()
    
    def _setup_service(self):
        """Initialize Google Sheets service"""
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            print(f"❌ Failed to setup Google Sheets service: {e}")
            raise
    
    def log_alert(self, alert_data):
        """
        Log an alert to the Alerts tab
        
        Args:
            alert_data (dict): Alert data with keys:
                - tweet_id: Tweet ID
                - contract_ticker: Contract ticker
                - sps_score: SPS score
                - similarity_score: Similarity score
                - sentiment_score: Sentiment score
                - certainty_score: Certainty score
                - source_weight: Source weight
                - username: Twitter username
                - tweet_text: Tweet text (will be truncated to 200 chars)
        """
        try:
            # Prepare the row data
            timestamp = datetime.now(timezone.utc).isoformat()
            tweet_text = alert_data.get('tweet_text', '')
            
            # Truncate tweet text to 200 characters if needed
            if len(tweet_text) > 200:
                tweet_text = tweet_text[:197] + "..."
            
            row_data = [
                timestamp,                                    # A: Timestamp
                alert_data.get('tweet_id', ''),              # B: Tweet ID
                alert_data.get('contract_ticker', ''),       # C: Contract Ticker
                alert_data.get('sps_score', ''),             # D: SPS Score
                alert_data.get('similarity_score', ''),      # E: Similarity Score
                alert_data.get('sentiment_score', ''),       # F: Sentiment Score
                alert_data.get('certainty_score', ''),       # G: Certainty Score
                alert_data.get('source_weight', ''),         # H: Source Weight
                alert_data.get('username', ''),              # I: Username
                tweet_text                                   # J: Tweet Text
            ]
            
            # Append the row to the Alerts tab
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Alerts!A:J',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            print(f"✅ Alert logged: {alert_data.get('contract_ticker')} - SPS: {alert_data.get('sps_score')}")
            return True
            
        except HttpError as error:
            print(f"❌ HTTP Error logging alert: {error}")
            return False
        except Exception as error:
            print(f"❌ Unexpected error logging alert: {error}")
            return False
    
    def log_no_action(self, tweet_data, reason="SPS below threshold"):
        """
        Log a processed tweet to the No Action tab
        
        Args:
            tweet_data (dict): Tweet data with keys:
                - tweet_id: Tweet ID
                - contract_ticker: Contract ticker (if matched)
                - sps_score: SPS score
                - similarity_score: Similarity score
                - sentiment_score: Sentiment score
                - certainty_score: Certainty score
                - source_weight: Source weight
                - username: Twitter username
                - tweet_text: Tweet text
                - contract_title: Contract title (if matched)
            reason (str): Reason why no action was taken
        """
        try:
            # Prepare the row data for No Action tab
            timestamp = datetime.now(timezone.utc).isoformat()
            processing_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            tweet_text = tweet_data.get('tweet_text', '')
            
            # Truncate tweet text to 300 characters for No Action tab
            if len(tweet_text) > 300:
                tweet_text = tweet_text[:297] + "..."
            
            row_data = [
                timestamp,                                    # A: Timestamp
                tweet_data.get('tweet_id', ''),              # B: Tweet ID
                tweet_data.get('username', ''),              # C: Username
                tweet_text,                                  # D: Tweet Text
                tweet_data.get('contract_ticker', ''),       # E: Contract Ticker
                tweet_data.get('sps_score', ''),             # F: SPS Score
                tweet_data.get('similarity_score', ''),      # G: Similarity Score
                tweet_data.get('sentiment_score', ''),       # H: Sentiment Score
                tweet_data.get('certainty_score', ''),       # I: Certainty Score
                tweet_data.get('source_weight', ''),         # J: Source Weight
                reason,                                      # K: Reason
                processing_date,                             # L: Processing Date
                "X Following Feed",                          # M: Feed Source
                tweet_data.get('contract_title', ''),        # N: Contract Title
                ""                                           # O: Notes (empty for now)
            ]
            
            # Append the row to the No Action tab
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='No Action!A:O',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            print(f"📝 No Action logged: {tweet_data.get('username')} - SPS: {tweet_data.get('sps_score')} - {reason}")
            return True
            
        except HttpError as error:
            print(f"❌ HTTP Error logging no action: {error}")
            return False
        except Exception as error:
            print(f"❌ Unexpected error logging no action: {error}")
            return False
    
    def check_recent_alerts(self, contract_ticker, hours=6):
        """
        Check if a contract has been alerted on in the last N hours
        
        Args:
            contract_ticker (str): Contract ticker to check
            hours (int): Number of hours to look back
            
        Returns:
            bool: True if contract was recently alerted, False otherwise
        """
        try:
            # Read existing alerts
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Alerts!A:C'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only header or empty
                return False
            
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            
            # Check recent alerts for this contract
            for row in values[1:]:  # Skip header
                if len(row) >= 3:
                    try:
                        alert_timestamp = datetime.fromisoformat(row[0].replace('Z', '+00:00')).timestamp()
                        alert_contract = row[2]
                        
                        if alert_contract == contract_ticker and alert_timestamp > cutoff_time:
                            print(f"⚠️  Contract {contract_ticker} was recently alerted (within {hours} hours)")
                            return True
                    except (ValueError, IndexError):
                        continue
            
            return False
            
        except Exception as error:
            print(f"❌ Error checking recent alerts: {error}")
            return False
    
    def get_alert_count(self):
        """Get total number of alerts logged"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Alerts!A:A'
            ).execute()
            
            values = result.get('values', [])
            return max(0, len(values) - 1)  # Subtract header row
            
        except Exception as error:
            print(f"❌ Error getting alert count: {error}")
            return 0

def test_alerts_logger():
    """Test the alerts logger with sample data"""
    logger = AlertsLogger()
    
    # Test data
    test_alert = {
        'tweet_id': 'test_123456789',
        'contract_ticker': 'BIDEN-NOM-2024',
        'sps_score': 0.85,
        'similarity_score': 0.92,
        'sentiment_score': -0.9,
        'certainty_score': 0.95,
        'source_weight': 1.0,
        'username': '@JakeSherman',
        'tweet_text': 'BREAKING: Biden reportedly considering stepping aside. Talks underway this week with top Dems.'
    }
    
    print("Testing alerts logger...")
    
    # Test logging
    success = logger.log_alert(test_alert)
    if success:
        print("✅ Test alert logged successfully")
    
    # Test recent alerts check
    is_recent = logger.check_recent_alerts('BIDEN-NOM-2024', hours=6)
    print(f"Recent alert check: {is_recent}")
    
    # Test alert count
    count = logger.get_alert_count()
    print(f"Total alerts: {count}")

if __name__ == "__main__":
    test_alerts_logger()

