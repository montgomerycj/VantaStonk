#!/usr/bin/env python3
"""
VantaStonk v2 - Simplified for Permanent Deployment
Autonomous Alpha-Hunting Trading Assistant with 95v2 Strategy
"""

import json
import time
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

class VantaStonkAgent:
    def __init__(self):
        # Memory variables
        self.memory = {
            "watchlist": [],
            "thresholds": {},
            "shadowlist": ["ZETA", "AMPL", "MLYS", "ADSK"],  # Updated with user data
            "shadowListLog": [
                {"ticker": "ZETA", "date": "2025-07-12"},
                {"ticker": "AMPL", "date": "2025-07-11"},
                {"ticker": "MLYS", "date": "2025-07-11"},
                {"ticker": "ADSK", "date": "2025-07-11"}
            ],
            "myStonks": ["LAC", "ECL", "PYPL", "RPD", "ASAN", "ZETA", "HUBG", "CME", "OC", "LYTS", "WOR", "KE", "CSCO", "LOAR"],
            "glance_ideas": [
                {
                    "date": "2025-07-11",
                    "momentum": "Long ZETA",
                    "pair": "Long PYPL / Short SQ",
                    "macro": "Biotech sector on Fed rate expectations",
                    "hedge": "Short TSLA"
                },
                {
                    "date": "2025-07-12",
                    "momentum": "Long RPD",
                    "pair": "Long ASAN / Short OKTA",
                    "macro": "AI/infra boost after Nvidia call",
                    "hedge": "None"
                }
            ],
            "last_glance_date": "2025-07-12",
            "alert_log": []
        }
        
        # Message rate limiting
        self.message_timestamps = []
        self.max_messages_per_window = 20
        self.time_window_minutes = 10
        self.rate_limit_active = False
        self.rate_limit_end_time = None
        
        # Configuration
        self.telegram_bot_token = "7805619907:AAHc03y2OWJuYOpT-SLLO2sy5_I_JN5YNL8"
        self.telegram_chat_id = "213332819"
        self.memory_file = "/home/ubuntu/vantastonk_memory.json"  # Changed to persistent location
        
        # VantaStonk System Prompt
        self.vantastonk_personality = """VantaStonk — autonomous, alpha-hunting trading assistant built on 95v2 strategy.
        
95v2 Framework:
1. Momentum – Strong movement + catalysts, avoid >5% run-ups in 5 days
2. Pair Trades – Long/short combinations with fundamental divergence  
3. Macro Tilt – News/geopolitical triggers (Fed, oil, trade, conflict)
4. Defensive Hedges – Short setups, volatility plays, capital protection
5. ShadowList – Track stocks likely picked by AI quant funds
6. Avoid Textbook PEAD – Don't chase already-ran earnings plays

Aggressive brevity - think like a smart trader texting signals, not writing reports."""
        
        # Load persistent memory
        self.load_memory()
        
        # Initialize Flask app
        self.app = Flask(__name__)
        CORS(self.app)
        self.setup_routes()
        
        print("🚀 VantaStonk v2 Simplified - Alpha-hunting assistant initialized")
        # Removed automatic startup message to prevent spam
    
    def is_duplicate(self, ticker, myStonks, shadowListLog):
        """Check if ticker is duplicate in myStonks or shadowListLog"""
        ticker = ticker.upper()
        stonks = [t.upper() for t in myStonks]
        shadowed = [entry["ticker"].upper() for entry in shadowListLog]
        return ticker in stonks or ticker in shadowed
    
    def get_stock_price(self, ticker):
        """Get current stock price using Yahoo Finance API"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'chart' not in data or not data['chart']['result']:
                return None
                
            result = data['chart']['result'][0]
            
            # Extract price data
            quote = result['indicators']['quote'][0]
            open_prices = quote.get('open', [])
            close_prices = quote.get('close', [])
            
            if not open_prices or not close_prices:
                return None
            
            # Get latest prices
            open_price = open_prices[0] if open_prices[0] is not None else open_prices[-1]
            current_price = close_prices[-1]
            
            if open_price is None or current_price is None:
                return None
                
            change_percent = ((current_price - open_price) / open_price) * 100
            
            return {
                'ticker': ticker.upper(),
                'current_price': round(current_price, 2),
                'open_price': round(open_price, 2),
                'change_percent': round(change_percent, 2),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")
            return None
    
    def setup_routes(self):
        
        @self.app.route('/', methods=['GET'])
        def home():
            """Home page"""
            return jsonify({
                "agent": "VantaStonk v2",
                "strategy": "95v2",
                "status": "permanently deployed",
                "description": "Autonomous alpha-hunting trading assistant",
                "endpoints": {
                    "webhook": "/webhook",
                    "health": "/health", 
                    "status": "/status",
                    "trigger_glance": "/trigger-glance"
                }
            })
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Handle incoming Telegram messages"""
            try:
                data = request.get_json()
                
                if 'message' in data:
                    message = data['message']
                    chat_id = str(message['chat']['id'])
                    text = message.get('text', '')
                    
                    if chat_id == self.telegram_chat_id:
                        print(f"📨 Received: {text}")
                        response = self.process_command(text)
                        if response:
                            self.send_telegram_message(response)
                    
                return jsonify({"status": "ok"})
                
            except Exception as e:
                print(f"❌ Webhook error: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check"""
            return jsonify({
                "status": "healthy",
                "agent": "VantaStonk v2",
                "strategy": "95v2",
                "deployment": "permanent",
                "watchlist_count": len(self.memory['watchlist']),
                "shadowlist_count": len(self.memory['shadowlist']),
                "shadowlist_log_count": len(self.memory['shadowListLog']),
                "my_stonks_count": len(self.memory['myStonks']),
                "glance_ideas_count": len(self.memory['glance_ideas']),
                "rate_limit_active": self.rate_limit_active,
                "last_glance": self.memory['last_glance_date']
            })
        
        @self.app.route('/status', methods=['GET'])
        def status():
            """Detailed status"""
            return jsonify({
                "memory": self.memory,
                "rate_limit_active": self.rate_limit_active,
                "message_count_last_10min": len(self.message_timestamps),
                "personality": self.vantastonk_personality
            })
        
        @self.app.route('/trigger-glance', methods=['POST'])
        def trigger_glance():
            """Manual glance trigger"""
            self.generate_daily_glance()
            return jsonify({"status": "glance_triggered"})
    
    def check_rate_limit(self) -> bool:
        """Check message rate limit"""
        current_time = datetime.now()
        
        if self.rate_limit_active and current_time < self.rate_limit_end_time:
            return False
        elif self.rate_limit_active and current_time >= self.rate_limit_end_time:
            self.rate_limit_active = False
            self.rate_limit_end_time = None
            self.message_timestamps = []
            print("✅ Rate limit ended")
        
        cutoff_time = current_time - timedelta(minutes=self.time_window_minutes)
        self.message_timestamps = [ts for ts in self.message_timestamps if ts > cutoff_time]
        
        if len(self.message_timestamps) >= self.max_messages_per_window:
            self.rate_limit_active = True
            self.rate_limit_end_time = current_time + timedelta(minutes=self.time_window_minutes)
            
            warning_msg = f"⚠️ RATE LIMIT: 20 msgs/10min reached. Pausing until {self.rate_limit_end_time.strftime('%H:%M')}"
            self._send_telegram_direct(warning_msg)
            return False
        
        return True
    
    def send_telegram_message(self, message: str) -> bool:
        """Send message with rate limiting"""
        if not self.check_rate_limit():
            print(f"🚫 Rate limited: {message[:30]}...")
            return False
        
        success = self._send_telegram_direct(message)
        if success:
            self.message_timestamps.append(datetime.now())
        return success
    
    def _send_telegram_direct(self, message: str) -> bool:
        """Send message directly to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Sent: {message[:30]}...")
                return True
            else:
                print(f"❌ Telegram error {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Send error: {e}")
            return False
    
    def fetch_stock_data(self, ticker: str) -> Optional[Dict]:
        """Fetch stock data from Yahoo Finance"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Yahoo error for {ticker}: {response.status_code}")
                return None
            
            data = response.json()
            result = data['chart']['result'][0]
            
            opens = result['indicators']['quote'][0]['open']
            closes = result['indicators']['quote'][0]['close']
            volumes = result['indicators']['quote'][0]['volume']
            
            valid_closes = [c for c in closes if c is not None]
            valid_opens = [o for o in opens if o is not None]
            valid_volumes = [v for v in volumes if v is not None]
            
            if not valid_closes or not valid_opens:
                return None
            
            current_price = valid_closes[-1]
            open_price = valid_opens[-1]
            
            five_day_change = 0
            if len(valid_closes) >= 5:
                five_day_change = ((current_price - valid_closes[-5]) / valid_closes[-5]) * 100
            
            avg_volume = sum(valid_volumes[-5:]) / min(len(valid_volumes), 5) if valid_volumes else 0
            current_volume = valid_volumes[-1] if valid_volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            return {
                'ticker': ticker,
                'open': open_price,
                'current': current_price,
                'five_day_change': five_day_change,
                'volume_ratio': volume_ratio,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")
            return None
    
    def check_price_alerts(self):
        """Check watchlist for alerts"""
        if self.rate_limit_active:
            print("🚫 Skipping scan - rate limited")
            return
        
        print(f"🔍 Scanning {len(self.memory['watchlist'])} tickers...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_alerts = [alert for alert in self.memory['alert_log'] if alert.get('date', '').startswith(today)]
        today_tickers = [alert['ticker'] for alert in today_alerts]
        
        alerts_sent = 0
        
        for ticker in self.memory['watchlist']:
            if ticker in today_tickers:
                continue
            
            if ticker not in self.memory['thresholds']:
                continue
            
            stock_data = self.fetch_stock_data(ticker)
            if not stock_data:
                continue
            
            open_price = stock_data['open']
            current_price = stock_data['current']
            percent_change = ((current_price - open_price) / open_price) * 100
            five_day_change = stock_data['five_day_change']
            volume_ratio = stock_data['volume_ratio']
            
            threshold = self.memory['thresholds'][ticker]
            if percent_change < -abs(threshold):
                # 95v2 logic - avoid if already ran >5% in 5 days
                if five_day_change > 5:
                    print(f"⏭️ {ticker} dropped but ran {five_day_change:.1f}% in 5d - skipping")
                    continue
                
                alert_message = f"🚨 {ticker} -{abs(percent_change):.1f}% | ${open_price:.2f}→${current_price:.2f}"
                
                if volume_ratio > 2:
                    alert_message += f" | Vol {volume_ratio:.1f}x"
                
                alert_message += " | Entry setup?"
                
                if self.send_telegram_message(alert_message):
                    alert_entry = {
                        'ticker': ticker,
                        'date': datetime.now().isoformat(),
                        'percent_change': percent_change,
                        'open_price': open_price,
                        'current_price': current_price,
                        'threshold': threshold,
                        'five_day_change': five_day_change,
                        'volume_ratio': volume_ratio
                    }
                    self.memory['alert_log'].append(alert_entry)
                    alerts_sent += 1
                    print(f"🚨 Alert sent for {ticker}")
            
            time.sleep(0.5)
        
        self.save_memory()
        print(f"✅ Scan complete. Alerts: {alerts_sent}")
    
    def scan_watchlist_prices(self):
        """Scan watchlist for price movements and send alerts"""
        if self.rate_limit_active:
            print("🚫 Skipping price scan - rate limited")
            return
        
        if not self.memory['watchlist']:
            print("📋 No tickers in watchlist to scan")
            return
        
        print(f"📊 Scanning {len(self.memory['watchlist'])} watchlist tickers...")
        alerts_sent = 0
        
        for ticker in self.memory['watchlist']:
            try:
                price_data = self.get_stock_price(ticker)
                
                if not price_data:
                    print(f"⚠️ Failed to get price for {ticker}")
                    continue
                
                current_price = price_data['current_price']
                change_percent = price_data['change_percent']
                
                # Check if we have a threshold for this ticker
                threshold = self.memory['thresholds'].get(ticker)
                if not threshold:
                    print(f"ℹ️ {ticker}: ${current_price} ({change_percent:+.1f}%) - No threshold set")
                    continue
                
                # Check if threshold is breached
                if abs(change_percent) >= threshold:
                    # Check if we already alerted today
                    today = datetime.now().strftime('%Y-%m-%d')
                    alert_key = f"{ticker}_{today}_{threshold}"
                    
                    if alert_key in self.memory['alert_log']:
                        print(f"⏭️ {ticker} alert already sent today")
                        continue
                    
                    # Generate alert message
                    direction = "📈" if change_percent > 0 else "📉"
                    alert_msg = f"{direction} {ticker} Alert!\n${current_price} ({change_percent:+.1f}%)\nThreshold: {threshold}%"
                    
                    # Send alert
                    if self.send_telegram_message(alert_msg):
                        self.memory['alert_log'].append(alert_key)
                        alerts_sent += 1
                        print(f"🚨 Alert sent: {ticker} {change_percent:+.1f}%")
                    else:
                        print(f"❌ Failed to send alert for {ticker}")
                else:
                    print(f"✅ {ticker}: ${current_price} ({change_percent:+.1f}%) - Within threshold ({threshold}%)")
                
                # Small delay between requests
                import time
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error scanning {ticker}: {e}")
        
        self.save_memory()
        print(f"✅ Scan complete. Alerts: {alerts_sent}")
    
    def is_market_hours(self):
        """Check if market is open (basic implementation)"""
        now = datetime.now()
        
        # Skip weekends
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Basic market hours check (9:30 AM - 4:00 PM ET)
        # This is simplified - doesn't account for holidays
        hour = now.hour
        return 9 <= hour <= 16
    
    def generate_daily_glance(self):
        if self.rate_limit_active:
            print("🚫 Skipping glance - rate limited")
            return
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self.memory['last_glance_date'] == today:
            print("⏭️ Glance already done today")
            return
        
        print("📊 Running simplified 95v2 Glance with duplicate checking...")
        
        # Sample tickers for glance ideas (would normally come from market analysis)
        candidate_momentum = ["SPY", "QQQ", "IWM", "XLF", "XLK", "NVDA", "MSFT", "GOOGL"]
        candidate_long = ["AAPL", "AMZN", "TSLA", "META", "NFLX", "CRM", "SHOP"]
        candidate_short = ["SNAP", "UBER", "LYFT", "ROKU", "COIN", "HOOD"]
        
        # Find non-duplicate tickers
        momentum_ticker = None
        for ticker in candidate_momentum:
            if not self.is_duplicate(ticker, self.memory['myStonks'], self.memory['shadowListLog']):
                momentum_ticker = ticker
                break
        
        pair_long = None
        for ticker in candidate_long:
            if not self.is_duplicate(ticker, self.memory['myStonks'], self.memory['shadowListLog']):
                pair_long = ticker
                break
        
        pair_short = None
        for ticker in candidate_short:
            if not self.is_duplicate(ticker, self.memory['myStonks'], self.memory['shadowListLog']):
                pair_short = ticker
                break
        
        # Check if we found valid non-duplicate tickers
        if not momentum_ticker or not pair_long or not pair_short:
            warning_msg = "⚠️ All candidate tickers are already in myStonks or ShadowList — no new unique idea generated."
            if self.send_telegram_message(warning_msg):
                print("⚠️ No unique tickers available for glance")
            return
        
        # Generate glance with unique tickers
        glance_summary = f"""📊 Glance: {today.replace('-', '/')}
• Momentum: Long {momentum_ticker} (market strength)
• Pair: Long {pair_long} / Short {pair_short}
• Macro Tilt: Tech rotation on rate expectations
• Hedge: VIX calls if market overextended"""
        
        glance_entry = {
            'date': today,
            'summary': glance_summary,
            'momentum': momentum_ticker,
            'pair_long': pair_long,
            'pair_short': pair_short,
            'macro': 'Tech rotation on rate expectations',
            'hedge': 'VIX calls if overextended',
            'timestamp': datetime.now().isoformat(),
            'type': 'simplified_with_duplicate_check'
        }
        
        self.memory['glance_ideas'].append(glance_entry)
        
        # Keep only last 30 days
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.memory['glance_ideas'] = [
            idea for idea in self.memory['glance_ideas'] 
            if idea.get('date', '') >= cutoff_date
        ]
        
        self.memory['last_glance_date'] = today
        
        if self.send_telegram_message(glance_summary):
            self.save_memory()
            print("✅ Unique glance sent")
        else:
            print("❌ Failed to send glance")
    
    def process_command(self, command: str) -> str:
        """Process commands with VantaStonk personality"""
        cmd = command.lower().strip()
        
        # Add to watchlist
        if "add" in cmd and ("watchlist" in cmd or "watch" in cmd):
            words = command.upper().split()
            for word in words:
                if word.isalpha() and len(word) <= 5 and word not in ['ADD', 'TO', 'WATCHLIST', 'WATCH']:
                    ticker = word.upper()
                    if ticker not in self.memory['watchlist']:
                        self.memory['watchlist'].append(ticker)
                        self.save_memory()
                        return f"✅ {ticker} added to watchlist"
                    else:
                        return f"ℹ️ {ticker} already watching"
            return "❓ No valid ticker found"
        
        # Add to shadowlist with logging and duplicate checking
        if "add" in cmd and ("shadow" in cmd or "shadowlist" in cmd):
            words = command.upper().split()
            for word in words:
                if word.isalpha() and len(word) <= 5 and word not in ['ADD', 'TO', 'SHADOW', 'SHADOWLIST', 'THE']:
                    ticker = word.upper()
                    
                    # Check for duplicates using cleaner function
                    if self.is_duplicate(ticker, self.memory['myStonks'], self.memory['shadowListLog']):
                        return f"⚠️ {ticker} already exists in myStonks or ShadowList — no duplicate added"
                    
                    # Add to shadowListLog with timestamp
                    today = datetime.now().strftime('%Y-%m-%d')
                    log_entry = {
                        "ticker": ticker,
                        "date": today
                    }
                    self.memory['shadowListLog'].append(log_entry)
                    
                    # Also add to regular shadowlist for compatibility
                    if ticker not in self.memory['shadowlist']:
                        self.memory['shadowlist'].append(ticker)
                    
                    self.save_memory()
                    return f"👁️ {ticker} added to ShadowList (logged {today})"
            return "❓ No valid ticker found"
        
        # Set threshold
        if "set" in cmd and "threshold" in cmd:
            words = command.upper().split()
            ticker = None
            threshold = None
            
            for word in words:
                if word.isalpha() and len(word) <= 5 and word not in ['SET', 'THRESHOLD', 'AT']:
                    ticker = word.upper()
                elif word.replace('.', '').replace('-', '').isdigit():
                    threshold = float(word)
            
            if ticker and threshold:
                self.memory['thresholds'][ticker] = threshold
                if ticker not in self.memory['watchlist']:
                    self.memory['watchlist'].append(ticker)
                self.save_memory()
                return f"🎯 {ticker} threshold set to {threshold}%"
            return "❓ Need ticker and threshold number"
        
        # Show my positions
        if "my" in cmd and ("stonks" in cmd or "positions" in cmd or "holdings" in cmd):
            if self.memory['myStonks']:
                tickers = ", ".join(self.memory['myStonks'])
                return f"💼 My Stonks ({len(self.memory['myStonks'])}): {tickers}"
            return "💼 No positions tracked"
        
        # Show watchlist
        if "watchlist" in cmd or "watch" in cmd:
            if self.memory['watchlist']:
                tickers = ", ".join(self.memory['watchlist'])
                return f"📋 Watching: {tickers}"
            return "📋 Watchlist empty"
        
        # Show shadowlist
        if "shadow" in cmd and not "add" in cmd:
            if "log" in cmd:
                # Show detailed shadowListLog with dates
                if self.memory['shadowListLog']:
                    result = "👁️ ShadowList Log (detailed):\n"
                    for entry in self.memory['shadowListLog'][-10:]:  # Show last 10
                        result += f"• {entry['ticker']} ({entry['date']})\n"
                    return result.strip()
                return "👁️ ShadowList log empty"
            elif "compact" in cmd:
                # Compact format
                if self.memory['shadowListLog']:
                    tickers = [entry['ticker'] for entry in self.memory['shadowListLog']]
                    return f"ShadowList: {', '.join(tickers)}"
                return "ShadowList: (empty)"
            else:
                # Default clean summary format
                if self.memory['shadowListLog']:
                    result = "🕵️‍♂️ ShadowList:\n"
                    for entry in self.memory['shadowListLog']:
                        # Convert date to readable format (July 12)
                        date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
                        readable_date = date_obj.strftime('%B %d').replace(' 0', ' ')
                        result += f"• {entry['ticker']} (added {readable_date})\n"
                    return result.strip()
                return "🕵️‍♂️ ShadowList: (empty)"
        
        # Show last glance reports
        if "glance" in cmd and ("last" in cmd or "show" in cmd):
            count = 3
            if "1" in cmd:
                count = 1
            elif "2" in cmd:
                count = 2
            elif "5" in cmd:
                count = 5
            
            recent_glances = self.memory['glance_ideas'][-count:] if self.memory['glance_ideas'] else []
            if recent_glances:
                result = f"📊 Last {len(recent_glances)} Glance(s):\n\n"
                for glance in recent_glances:
                    result += glance.get('summary', 'No summary') + "\n\n"
                return result.strip()
            return "📊 No glance reports yet"
        
        # Run glance now
        if "run glance" in cmd or "glance now" in cmd:
            self.generate_daily_glance()
            return "📊 Glance scan triggered"
        
        # Status
        if "status" in cmd:
            rate_status = "🚫 LIMITED" if self.rate_limit_active else "✅ Active"
            today_alerts = len([a for a in self.memory['alert_log'] if a.get('date', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
            return (
                f"🤖 VantaStonk v2 Status:\n"
                f"Strategy: 95v2\n"
                f"Deployment: Permanent\n"
                f"Rate Limit: {rate_status}\n"
                f"Watchlist: {len(self.memory['watchlist'])}\n"
                f"Shadowlist: {len(self.memory['shadowlist'])}\n"
                f"Alerts Today: {today_alerts}\n"
                f"Last Glance: {self.memory['last_glance_date'] or 'Never'}"
            )
        
        # Clear alerts
        if "clear alert" in cmd:
            self.memory['alert_log'] = []
            self.save_memory()
            return "✅ Alert log cleared"
        
        # Test price command
        if "test price" in cmd:
            words = command.upper().split()
            for word in words:
                if word.isalpha() and len(word) <= 5 and word not in ['TEST', 'PRICE']:
                    ticker = word.upper()
                    price_data = self.get_stock_price(ticker)
                    if price_data:
                        return f"💰 {ticker}: ${price_data['current_price']} ({price_data['change_percent']:+.1f}%)"
                    else:
                        return f"❌ Failed to get price for {ticker}"
            return "❓ Usage: 'test price AAPL'"
        
        # Manual price scan
        if "scan prices" in cmd or "price scan" in cmd:
            if not self.memory['watchlist']:
                return "📋 Watchlist empty - add tickers first"
            
            # Run immediate scan
            import threading
            scan_thread = threading.Thread(target=self.scan_watchlist_prices, daemon=True)
            scan_thread.start()
            return f"📊 Price scan started for {len(self.memory['watchlist'])} tickers"
        
        # Help
        if "help" in cmd or cmd == "":
            return (
                "🤖 VantaStonk v2 Commands:\n\n"
                "📋 Watchlist:\n"
                "• 'Add AAPL to watchlist'\n"
                "• 'Set AAPL threshold at 5'\n"
                "• 'Show watchlist'\n\n"
                "💼 My Positions:\n"
                "• 'Show my stonks'\n"
                "• 'Show my positions'\n\n"
                "👁️ ShadowList:\n"
                "• 'Add TSLA to the ShadowList'\n"
                "• 'Show ShadowList' (clean format)\n"
                "• 'Show ShadowList compact'\n"
                "• 'Show ShadowList log' (detailed)\n\n"
                "📊 Glance:\n"
                "• 'Run glance now'\n"
                "• 'Show last 3 glance reports'\n\n"
                "ℹ️ Other:\n"
                "• 'Status'\n"
                "• 'Clear alerts'"
            )
        
        return "❓ Unknown command. Send 'help' for options."
    
    def save_memory(self):
        """Save memory to file"""
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.memory, f, indent=2)
            print("💾 Memory saved")
        except Exception as e:
            print(f"❌ Save error: {e}")
    
    def load_memory(self):
        """Load memory from file"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    loaded_memory = json.load(f)
                    self.memory.update(loaded_memory)
                print("💾 Memory loaded")
            else:
                print("💾 Starting fresh")
        except Exception as e:
            print(f"❌ Load error: {e}")
    
    def start_background_tasks(self):
        """Start background monitoring tasks"""
        def monitor_loop():
            while True:
                try:
                    # Check prices every 10 minutes
                    self.check_price_alerts()
                    time.sleep(600)  # 10 minutes
                except Exception as e:
                    print(f"❌ Monitor error: {e}")
                    time.sleep(60)
        
        def glance_loop():
            while True:
                try:
                    current_time = datetime.now()
                    # Check if it's 3 PM
                    if current_time.hour == 15 and current_time.minute == 0:
                        self.generate_daily_glance()
                        time.sleep(3600)  # Wait an hour to avoid duplicate
                    else:
                        time.sleep(60)  # Check every minute
                except Exception as e:
                    print(f"❌ Glance error: {e}")
                    time.sleep(60)
        
        # Start background threads
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        glance_thread = threading.Thread(target=glance_loop, daemon=True)
        
        monitor_thread.start()
        glance_thread.start()
        
        print("⏰ Background tasks started: 10min scans, 3PM glance")
    
    def start_background_tasks(self):
        """Start background price monitoring and daily glance"""
        import threading
        import time
        
        def price_monitor():
            """Background thread for price monitoring"""
            while True:
                try:
                    if self.is_market_hours():
                        print("📊 Running 10-minute price scan...")
                        self.scan_watchlist_prices()
                    else:
                        print("🕐 Market closed - skipping price scan")
                    
                    # Wait 10 minutes
                    time.sleep(600)  # 600 seconds = 10 minutes
                    
                except Exception as e:
                    print(f"❌ Price monitor error: {e}")
                    time.sleep(60)  # Wait 1 minute on error
        
        def daily_glance_monitor():
            """Background thread for daily glance at 3 PM"""
            while True:
                try:
                    now = datetime.now()
                    if now.hour == 15 and now.minute < 10:  # 3:00-3:10 PM window
                        print("📊 Running daily glance...")
                        self.generate_daily_glance()
                        # Sleep until next day to avoid multiple runs
                        time.sleep(3600)  # 1 hour
                    else:
                        time.sleep(300)  # Check every 5 minutes
                        
                except Exception as e:
                    print(f"❌ Daily glance error: {e}")
                    time.sleep(300)
        
        # Start background threads
        price_thread = threading.Thread(target=price_monitor, daemon=True)
        glance_thread = threading.Thread(target=daily_glance_monitor, daemon=True)
        
        price_thread.start()
        glance_thread.start()
        
        print("🚀 Background tasks started: price monitoring + daily glance")
    
    def run(self):
        print("🚀 Starting VantaStonk v2 Simplified...")
        
        # Start background tasks
        self.start_background_tasks()
        
        print("✅ VantaStonk v2 running permanently!")
        print("📊 95v2 strategy active")
        print("🌐 Endpoints: /, /webhook, /health, /status")
        
        # Run Flask app
        self.app.run(host='0.0.0.0', port=5000, debug=False)

# Create the agent instance
agent = VantaStonkAgent()

# Flask app for deployment
app = agent.app

# Start background tasks
agent.start_background_tasks()

# Create and run the agent
if __name__ == "__main__":
    agent.run()

