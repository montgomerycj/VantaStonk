#!/usr/bin/env python3
"""
Remove handles from SourceWeights that are no longer followed on X
"""

import sys
import gspread
from google.oauth2.service_account import Credentials

class UnfollowedHandlesRemover:
    def __init__(self):
        # Google Sheets setup
        self.sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
        self.credentials_path = "/home/ubuntu/google_credentials.json"
        self.setup_google_sheets()
        
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
    
    def get_current_follows(self):
        """Get current X follows list"""
        # Current follows based on browser observation
        current_follows = [
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
        return [handle.lower() for handle in current_follows]
    
    def remove_unfollowed(self):
        """Remove handles that are no longer followed"""
        try:
            current_follows = self.get_current_follows()
            
            # Get all current data from sheet
            all_values = self.source_weights_tab.get_all_values()
            
            # Find rows to delete
            rows_to_delete = []
            
            for i, row in enumerate(all_values[1:], start=2):  # Skip header, start from row 2
                if row and len(row) > 0:
                    handle = row[0].strip().lower()
                    if handle and handle not in current_follows:
                        rows_to_delete.append((i, handle))
                        print(f"🗑️  Found unfollowed handle: {handle}")
            
            if not rows_to_delete:
                print("✅ No unfollowed handles found")
                return
            
            # Confirm deletion
            print(f"\n⚠️  Found {len(rows_to_delete)} unfollowed handles to remove:")
            for _, handle in rows_to_delete:
                print(f"   - {handle}")
            
            confirm = input("\nProceed with deletion? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Deletion cancelled")
                return
            
            # Delete rows in reverse order to maintain row numbers
            for row_num, handle in reversed(rows_to_delete):
                self.source_weights_tab.delete_rows(row_num)
                print(f"🗑️  Removed: {handle}")
            
            print(f"✅ Successfully removed {len(rows_to_delete)} unfollowed handles")
            
        except Exception as e:
            print(f"❌ Error removing unfollowed handles: {e}")

def main():
    """Main function"""
    remover = UnfollowedHandlesRemover()
    remover.remove_unfollowed()

if __name__ == "__main__":
    main()

