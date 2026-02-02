#!/usr/bin/env python3
"""
Update SourceWeights tab with new X follows while preserving existing data
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials

class XFollowsUpdater:
    def __init__(self):
        # Google Sheets setup
        self.sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
        self.credentials_path = "/home/ubuntu/google_credentials.json"
        self.setup_google_sheets()
        
        # Default values for new follows
        self.default_tier = 1
        self.default_weight = 0.8
        self.default_notes = "Auto-added from X follows"
        
    def setup_google_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scope
            )
            
            self.gc = gspread.authorize(credentials)
            self.sheet = self.gc.open_by_key(self.sheet_id)
            self.source_weights_tab = self.sheet.worksheet("SourceWeights")
            
            print("✅ Google Sheets connection established")
            
        except Exception as e:
            print(f"❌ Failed to setup Google Sheets: {e}")
            sys.exit(1)
    
    def get_existing_handles(self):
        """Get existing handles from SourceWeights tab"""
        try:
            # Get all values from column A (handles)
            handles_column = self.source_weights_tab.col_values(1)
            
            # Remove header and clean handles
            existing_handles = []
            for handle in handles_column[1:]:  # Skip header
                if handle.strip():
                    # Ensure handle starts with @
                    clean_handle = handle.strip()
                    if not clean_handle.startswith('@'):
                        clean_handle = '@' + clean_handle
                    existing_handles.append(clean_handle.lower())
            
            print(f"📊 Found {len(existing_handles)} existing handles in SourceWeights")
            return existing_handles
            
        except Exception as e:
            print(f"❌ Error getting existing handles: {e}")
            return []
    
    def extract_x_follows_browser(self):
        """Extract follows from X using browser automation"""
        try:
            print("🌐 Starting browser to extract X follows...")
            
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Start browser
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 20)
            
            # Navigate to following page
            driver.get("https://x.com/Poliseo84/following")
            time.sleep(5)
            
            # Extract handles from page
            follows = set()
            scroll_attempts = 0
            max_scrolls = 10
            
            while scroll_attempts < max_scrolls:
                # Find all handle elements
                handle_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, '/') and starts-with(text(), '@')]")
                
                for element in handle_elements:
                    handle = element.text.strip()
                    if handle.startswith('@') and len(handle) > 1:
                        follows.add(handle.lower())
                
                # Scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                scroll_attempts += 1
                
                print(f"📜 Scroll {scroll_attempts}: Found {len(follows)} handles so far")
            
            driver.quit()
            
            print(f"✅ Extracted {len(follows)} handles from X following list")
            return list(follows)
            
        except Exception as e:
            print(f"❌ Error extracting X follows: {e}")
            return []
    
    def extract_x_follows_simple(self):
        """Simple extraction method - manually defined list for testing"""
        # Based on what we saw in the browser, here are the handles
        follows = [
            '@edokeefe', '@spectatorindex', '@epaleezeldin', '@DailyNewsJustIn',
            '@ElectionWiz', '@ben_d_lazarus', '@atlas_intel', '@KobeissiLetter',
            '@GRDecter', '@StealthQE4', '@PredictIt', '@emckowndawson', '@JayShams',
            '@elwasson', '@ZcohenCNN', '@JakeSherman', '@jeannasmialek', '@NickTimiraos',
            '@politico', '@ZoeTillman', '@kyledcheney', '@DemocracyDocket', '@SCOTUSblog',
            '@Redistrict', '@DecisionDeskHQ', '@ElectionHQ', '@simonateba', '@alerts_chat',
            '@Kalshi', '@kalshiwhales', '@singsingkix', '@PolymarktWhales', '@Polymarket',
            '@NateSilver538', '@RepLuna', '@nicksortor', '@WSJ', '@realDonaldTrump',
            '@RapidResponse47', '@JudicialWatch', '@TomFitton', '@cnnbrk', '@PressSec',
            '@SecRubio', '@LauraLoomer'
        ]
        
        # Convert to lowercase for comparison
        follows = [handle.lower() for handle in follows]
        
        print(f"📋 Using predefined list of {len(follows)} handles")
        return follows
    
    def find_new_handles(self, x_follows, existing_handles):
        """Find handles that are in X follows but not in SourceWeights"""
        new_handles = []
        
        for handle in x_follows:
            if handle.lower() not in [h.lower() for h in existing_handles]:
                new_handles.append(handle)
        
        print(f"🆕 Found {len(new_handles)} new handles to add")
        if new_handles:
            print("New handles:", new_handles)
        
        return new_handles
    
    def add_new_handles_to_sheet(self, new_handles):
        """Add new handles to SourceWeights tab with default values"""
        if not new_handles:
            print("✅ No new handles to add")
            return
        
        try:
            # Get current data to find next empty row
            all_values = self.source_weights_tab.get_all_values()
            next_row = len(all_values) + 1
            
            # Prepare batch update data
            updates = []
            
            for i, handle in enumerate(new_handles):
                row_num = next_row + i
                
                # Ensure handle starts with @
                clean_handle = handle if handle.startswith('@') else '@' + handle
                
                # Prepare row data
                row_data = [
                    clean_handle,           # Column A: Handle
                    self.default_tier,      # Column B: Tier
                    self.default_weight,    # Column C: Weight
                    self.default_notes      # Column D: Notes
                ]
                
                # Add to batch update
                range_name = f"A{row_num}:D{row_num}"
                updates.append({
                    'range': range_name,
                    'values': [row_data]
                })
            
            # Execute batch update
            self.source_weights_tab.batch_update(updates)
            
            print(f"✅ Successfully added {len(new_handles)} new handles to SourceWeights")
            print(f"   Default Tier: {self.default_tier}")
            print(f"   Default Weight: {self.default_weight}")
            
        except Exception as e:
            print(f"❌ Error adding new handles to sheet: {e}")
    
    def remove_unfollowed_handles(self, x_follows, existing_handles):
        """Remove handles from SourceWeights that are no longer followed"""
        try:
            # Get all current data
            all_values = self.source_weights_tab.get_all_values()
            
            # Find rows to delete (handles not in x_follows)
            rows_to_delete = []
            x_follows_lower = [h.lower() for h in x_follows]
            
            for i, row in enumerate(all_values[1:], start=2):  # Skip header, start from row 2
                if row and len(row) > 0:
                    handle = row[0].strip().lower()
                    if handle and handle not in x_follows_lower:
                        rows_to_delete.append(i)
                        print(f"🗑️  Will remove unfollowed handle: {handle}")
            
            # Delete rows in reverse order to maintain row numbers
            for row_num in reversed(rows_to_delete):
                self.source_weights_tab.delete_rows(row_num)
            
            if rows_to_delete:
                print(f"✅ Removed {len(rows_to_delete)} unfollowed handles")
            else:
                print("✅ No unfollowed handles to remove")
                
        except Exception as e:
            print(f"❌ Error removing unfollowed handles: {e}")
    
    def sync_follows(self, remove_unfollowed=False):
        """Main method to sync X follows with SourceWeights"""
        print("🔄 Starting X follows sync...")
        print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Get existing handles from sheet
        existing_handles = self.get_existing_handles()
        
        # Extract current X follows
        x_follows = self.extract_x_follows_simple()
        
        if not x_follows:
            print("❌ No follows extracted, aborting sync")
            return
        
        # Find new handles
        new_handles = self.find_new_handles(x_follows, existing_handles)
        
        # Add new handles
        self.add_new_handles_to_sheet(new_handles)
        
        # Optionally remove unfollowed handles
        if remove_unfollowed:
            self.remove_unfollowed_handles(x_follows, existing_handles)
        
        print("✅ X follows sync completed!")
        print(f"📊 Total handles in SourceWeights: {len(existing_handles) + len(new_handles)}")

def main():
    """Main function"""
    updater = XFollowsUpdater()
    
    # Check command line arguments
    remove_unfollowed = '--remove-unfollowed' in sys.argv
    
    # Run sync
    updater.sync_follows(remove_unfollowed=remove_unfollowed)

if __name__ == "__main__":
    main()

