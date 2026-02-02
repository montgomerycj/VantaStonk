#!/usr/bin/env python3
"""
Create No Action tab for storing all processed tweets regardless of SPS score
"""

import gspread
from google.oauth2.service_account import Credentials

def create_no_action_tab():
    """Create the No Action tab with appropriate headers"""
    
    # Google Sheets setup
    sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
    credentials_path = "/home/ubuntu/google_credentials.json"
    
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(
            credentials_path, 
            scopes=scope
        )
        
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_key(sheet_id)
        
        # Check if No Action tab already exists
        try:
            no_action_tab = sheet.worksheet("No Action")
            print("✅ No Action tab already exists")
            return
        except gspread.WorksheetNotFound:
            pass
        
        # Create the No Action tab
        no_action_tab = sheet.add_worksheet(title="No Action", rows=1000, cols=15)
        
        # Set up headers
        headers = [
            "Timestamp",           # A
            "Tweet ID",           # B  
            "Username",           # C
            "Tweet Text",         # D
            "Contract Ticker",    # E
            "SPS Score",          # F
            "Similarity Score",   # G
            "Sentiment Score",    # H
            "Certainty Score",    # I
            "Source Weight",      # J
            "Reason",             # K (why no action taken)
            "Processing Date",    # L
            "Feed Source",        # M
            "Contract Title",     # N
            "Notes"               # O
        ]
        
        # Add headers to first row
        no_action_tab.update('A1:O1', [headers])
        
        # Format headers (bold)
        no_action_tab.format('A1:O1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
        
        # Set column widths for better readability
        no_action_tab.batch_update([
            {
                'range': 'A:A',
                'values': [],
                'majorDimension': 'COLUMNS'
            }
        ])
        
        print("✅ Created No Action tab with headers")
        print("📊 Tab will store all processed tweets with SPS scores below 0.70")
        
    except Exception as e:
        print(f"❌ Error creating No Action tab: {e}")

if __name__ == "__main__":
    create_no_action_tab()

