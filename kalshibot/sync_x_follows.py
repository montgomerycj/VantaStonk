#!/usr/bin/env python3
"""
Sync X follows with SourceWeights tab - simplified version
"""

import sys
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

class XFollowsSync:
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
    
    def get_current_x_follows(self):
        """Get current X follows list based on browser observation"""
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
        
        print(f"📋 Current X follows: {len(follows)} handles")
        return follows
    
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
                    existing_handles.append(clean_handle)
            
            print(f"📊 Existing handles in SourceWeights: {len(existing_handles)}")
            return existing_handles
            
        except Exception as e:
            print(f"❌ Error getting existing handles: {e}")
            return []
    
    def find_new_handles(self, x_follows, existing_handles):
        """Find handles that are in X follows but not in SourceWeights"""
        new_handles = []
        existing_lower = [h.lower() for h in existing_handles]
        
        for handle in x_follows:
            if handle.lower() not in existing_lower:
                new_handles.append(handle)
        
        print(f"🆕 New handles to add: {len(new_handles)}")
        if new_handles:
            for handle in new_handles:
                print(f"   + {handle}")
        
        return new_handles
    
    def add_new_handles(self, new_handles):
        """Add new handles to SourceWeights tab"""
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
                
                # Prepare row data
                row_data = [
                    handle,                 # Column A: Handle
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
            
            print(f"✅ Successfully added {len(new_handles)} new handles")
            print(f"   Default Tier: {self.default_tier}")
            print(f"   Default Weight: {self.default_weight}")
            
        except Exception as e:
            print(f"❌ Error adding new handles: {e}")
    
    def sync(self):
        """Main sync method"""
        print("🔄 Starting X follows sync...")
        print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Get current data
        x_follows = self.get_current_x_follows()
        existing_handles = self.get_existing_handles()
        
        # Find and add new handles
        new_handles = self.find_new_handles(x_follows, existing_handles)
        self.add_new_handles(new_handles)
        
        # Summary
        total_handles = len(existing_handles) + len(new_handles)
        print(f"✅ Sync completed!")
        print(f"📊 Total handles in SourceWeights: {total_handles}")
        
        return len(new_handles)

def main():
    """Main function"""
    sync = XFollowsSync()
    new_count = sync.sync()
    
    if new_count > 0:
        print(f"\n🎉 Added {new_count} new handles with default values:")
        print(f"   Tier: 1")
        print(f"   Weight: 0.8")
        print(f"   Notes: Auto-added from X follows")

if __name__ == "__main__":
    main()

