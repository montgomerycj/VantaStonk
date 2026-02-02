#!/usr/bin/env python3
"""
Kalshi contract fetcher with authentication - fetches open markets and filters for relevant contracts
"""

import requests
import json
import time
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Kalshi API configuration
API_BASE = "https://api.elections.kalshi.com"
API_KEY_ID = "435dbdda-7393-4e9b-a9a0-938c6ae9153d"
PRIVATE_KEY_PATH = "/home/ubuntu/kalshibot/kalshi_private_key.pem"

def load_private_key():
    """Load the RSA private key"""
    with open(PRIVATE_KEY_PATH, 'rb') as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    return private_key

def create_signature(method, path, body=""):
    """Create signature for Kalshi API authentication"""
    private_key = load_private_key()
    
    # Create timestamp (milliseconds since epoch)
    timestamp = str(int(time.time() * 1000))
    
    # Create message to sign
    message = f"{timestamp}{method}{path}{body}"
    
    # Sign the message
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Base64 encode the signature
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    return timestamp, signature_b64

def make_authenticated_request(method, path, params=None, body=None):
    """Make an authenticated request to Kalshi API"""
    url = f"{API_BASE}{path}"
    
    # Prepare body
    body_str = json.dumps(body) if body else ""
    
    # Create signature
    timestamp, signature = create_signature(method, path, body_str)
    
    # Prepare headers
    headers = {
        'KALSHI-ACCESS-KEY': API_KEY_ID,
        'KALSHI-ACCESS-SIGNATURE': signature,
        'KALSHI-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }
    
    # Make request
    if method == 'GET':
        response = requests.get(url, headers=headers, params=params, timeout=30)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=body, timeout=30)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    response.raise_for_status()
    return response.json()

def fetch_kalshi_markets():
    """Fetch open markets from Kalshi API with authentication"""
    try:
        print("🔍 Fetching markets from Kalshi API (authenticated)...")
        
        # Fetch markets with authentication
        path = "/trade-api/v2/markets"
        params = {
            'status': 'open',
            'limit': 1000
        }
        
        data = make_authenticated_request('GET', path, params=params)
        markets = data.get('markets', [])
        
        print(f"✅ Fetched {len(markets)} open markets (authenticated)")
        return markets
        
    except Exception as e:
        print(f"❌ Error fetching Kalshi markets: {e}")
        return []

def filter_contracts(markets):
    """Filter contracts based on criteria"""
    
    # Keywords for political/macro/Fed content
    keywords = ['politics', 'macro', 'congress', 'fed', 'trump', 'election', 
                'president', 'senate', 'house', 'fomc', 'powell', 'rate',
                'policy', 'tariff', 'trade', 'economy', 'inflation', 'jobs', 
                'gdp', 'court', 'scotus', 'regulation']
    
    # Calculate date threshold (60 days from now)
    date_threshold = datetime.now(timezone.utc) + timedelta(days=60)
    
    filtered = []
    
    print(f"\n🔍 Filtering contracts...")
    print(f"   Price range: 0.10-0.80")
    print(f"   Expiration: Within 60 days")
    print(f"   Keywords: {', '.join(keywords)}")
    
    for i, market in enumerate(markets, 1):
        print(f"\n  📋 Market {i}: {market.get('ticker', 'N/A')}")
        
        # Extract data
        ticker = market.get('ticker', '')
        title = market.get('title', '')
        event_ticker = market.get('event_ticker', '')
        yes_bid = market.get('yes_bid', 0)
        no_bid = market.get('no_bid', 0)
        
        # Parse expiration
        try:
            exp_str = market.get('expiration_time', '')
            if exp_str:
                expiration = datetime.fromisoformat(exp_str.replace('Z', '+00:00'))
                days_until_exp = (expiration - datetime.now(timezone.utc)).days
            else:
                days_until_exp = 999
        except:
            days_until_exp = 999
        
        print(f"    💰 YES: {yes_bid:.3f}, NO: {no_bid:.3f}")
        print(f"    📅 Expires in: {days_until_exp} days")
        print(f"    🏷️  Category: {event_ticker}")
        
        # Check filters
        price_ok = (0.10 <= yes_bid <= 0.80) or (0.10 <= no_bid <= 0.80)
        exp_ok = days_until_exp <= 60
        
        # Check if category or title contains keywords
        text_to_check = f"{event_ticker} {title}".lower()
        keyword_ok = any(kw in text_to_check for kw in keywords)
        
        print(f"    ✅ Price filter: {price_ok}")
        print(f"    ✅ Expiration filter: {exp_ok}")
        print(f"    ✅ Category filter: {keyword_ok}")
        
        if price_ok and exp_ok and keyword_ok:
            print(f"    ✅ MATCH - Adding to watchlist")
            filtered.append({
                'ticker': ticker,
                'title': title,
                'category': event_ticker,
                'yes_price': yes_bid,
                'no_price': no_bid,
                'spread': abs(yes_bid - no_bid),
                'expiration_days': days_until_exp
            })
        else:
            print(f"    ⚠️  Partial match - not all criteria met")
    
    print(f"\n🎯 Filtered to {len(filtered)} contracts")
    return filtered

def update_google_sheet(contracts):
    """Update WatchlistContracts tab in Google Sheet"""
    try:
        sheet_id = "1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8"
        credentials_path = "/home/ubuntu/google_credentials.json"
        
        credentials = Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        
        # Prepare data rows
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        
        rows = []
        for contract in contracts:
            rows.append([
                contract['ticker'],
                contract['title'],
                contract['category'],
                contract['yes_price'],
                contract['no_price'],
                contract['spread'],
                timestamp,
                'FALSE'  # Manually Entered?
            ])
        
        if rows:
            # Clear existing data (keep header)
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range='WatchlistContracts!A2:H'
            ).execute()
            
            # Write new data
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='WatchlistContracts!A2',
                valueInputOption='RAW',
                body={'values': rows}
            ).execute()
            
            print(f"✅ Updated Google Sheet with {len(rows)} contracts")
        else:
            print("⚠️  No contracts to update in sheet")
            
    except Exception as e:
        print(f"❌ Error updating Google Sheet: {e}")

def main():
    """Main function"""
    print("Kalshi Contract Fetcher (Authenticated)")
    print("=" * 40)
    
    # Fetch markets
    markets = fetch_kalshi_markets()
    
    if not markets:
        print("⚠️  No markets fetched")
        return
    
    # Filter contracts
    filtered = filter_contracts(markets)
    
    if not filtered:
        print("⚠️  No contracts match filter criteria")
        return
    
    # Update sheet
    update_google_sheet(filtered)
    
    print("\n✅ Kalshi sync complete")

if __name__ == "__main__":
    main()
