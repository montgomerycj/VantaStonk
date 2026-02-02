# Kalshibot System Documentation

## Overview

Kalshibot is an AI-powered trading assistant for Kalshi prediction markets. The system monitors social media signals (Twitter/X), matches them with relevant Kalshi contracts, and generates trading alerts based on sentiment, certainty, and source credibility scoring.

## System Architecture

### Core Components

1. **Kalshi API Integration** - Fetches and filters prediction market contracts
2. **X (Twitter) Feed Monitor** - Extracts tweets from followed accounts
3. **Signal Processing System (SPS)** - Scores tweets for trading relevance
4. **Google Sheets Database** - Stores contracts, source weights, alerts, and signals
5. **Telegram Bot Interface** - Provides command-based control and real-time alerts

## Component Details

### 1. Kalshi API Integration

**File**: `kalshi_simple_fetcher.py`

**Purpose**: Fetch relevant political and economic prediction market contracts from Kalshi

**Authentication**:
- API Key ID: `435dbdda-7393-4e9b-a9a0-938c6ae9153d`
- Private Key: `/home/ubuntu/kalshibot/kalshi_private_key.pem`
- Uses RSA signature-based authentication

**Series Queried**:
- `KXFEDDECISION` - Federal Reserve rate decisions
- `KXELECTION` - Election outcomes
- `KXTRUMP` - Trump-related events
- `KXPOLITICS` - Political events
- `KXCONGRESS` - Congressional actions
- `KXSENATE` - Senate decisions
- `KXHOUSE` - House decisions
- `KXPRESIDENT` - Presidential actions
- `KXSUPREMECOURT` - Supreme Court decisions
- `KXECONOMY` - Economic indicators
- `KXINFLATION` - Inflation data
- `KXJOBS` - Employment data
- `KXGDP` - GDP data

**Filtering Criteria**:
- **Price Range**: 0.05-0.95 (5%-95% probability) - captures tradeable contracts with uncertainty
- **Expiration**: Within 150 days - focuses on near-term events
- **Keywords**: 22 political/economic terms (fed, election, congress, trump, policy, etc.)
- **All three criteria must pass** for a contract to be captured

**Output**: Updates `WatchlistContracts` tab in Google Sheets with matching contracts

**Key Discovery**: Kalshi organizes contracts into series. Direct querying by series ticker (e.g., `series_ticker=KXFEDDECISION`) is required to access political/economic contracts, as they don't appear in the first 1000 results of general market queries.

---

### 2. X (Twitter) Feed Monitor

**File**: `extract_tweets.py`

**Purpose**: Extract tweets from followed accounts and process them for trading signals

**Process**:
1. **Sync X Follows** - Automatically updates SourceWeights tab with newly followed accounts
2. **Extract Tweets** - Pulls latest tweets from @poliseo84 following feed
3. **Apply Source Weights** - Assigns credibility scores based on account tier
4. **Match to Contracts** - Compares tweet content with Kalshi contract titles
5. **Calculate SPS Score** - Generates Signal Processing Score for each tweet/contract pair

**Default Values for New Follows**:
- **Tier**: 1
- **Weight**: 0.8

**Integration**: Runs automatically before tweet processing on every "check our x feed" command

---

### 3. Signal Processing System (SPS)

**Purpose**: Score the trading relevance of social media signals

**Formula**:
```
SPS = Source_Weight × (Sentiment + Certainty) × Similarity
```

**Components**:

1. **Source Weight** (0.0-1.0)
   - Tier 1 sources: 1.0 (high credibility)
   - Tier 2 sources: 0.8 (moderate credibility)
   - Tier 3 sources: 0.6 (lower credibility)
   - Stored in `SourceWeights` tab

2. **Sentiment** (-1.0 to +1.0)
   - Positive sentiment: 0.0 to +1.0
   - Negative sentiment: -1.0 to 0.0
   - Neutral: 0.0

3. **Certainty** (0.0-1.0)
   - Definitive statements: 1.0
   - Moderate confidence: 0.5-0.7
   - Speculation: 0.0-0.4

4. **Similarity** (0.0-1.0)
   - Semantic similarity between tweet text and contract title
   - Uses keyword matching and context analysis

**Alert Threshold**: SPS ≥ 0.70

**Deduplication**: 6-hour window to prevent repeated alerts for the same contract

---

### 4. Google Sheets Database

**Sheet ID**: `1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8`

**Credentials**: `/home/ubuntu/google_credentials.json`

**Tabs**:

#### WatchlistContracts
- **Purpose**: Stores filtered Kalshi contracts
- **Columns**: Ticker, Title, Category, YES Price, NO Price, Spread, Last Updated, Manually Entered
- **Updated By**: `kalshi_simple_fetcher.py`

#### SourceWeights
- **Purpose**: Stores Twitter account credibility scores
- **Columns**: Handle, Tier, Weight, Category, Notes
- **Updated By**: `sync_x_follows.py` (auto-adds new follows)
- **Total Handles**: 45 (as of last sync)

#### Alerts
- **Purpose**: Stores high-confidence trading signals (SPS ≥ 0.70)
- **Columns**: Timestamp, Tweet ID, Username, Tweet Text, Contract Ticker, SPS Score, Similarity, Sentiment, Certainty, Source Weight, Reason, Processing Date, Feed Source
- **Updated By**: `extract_tweets.py`

#### No Action
- **Purpose**: Stores all processed tweets that didn't trigger alerts (SPS < 0.70)
- **Columns**: Same as Alerts tab
- **Purpose**: Provides transparency into why tweets didn't generate alerts
- **Updated By**: `extract_tweets.py`

#### SignalScoring
- **Purpose**: Detailed scoring breakdown for each tweet/contract pair
- **Updated By**: `extract_tweets.py`

#### SignalCluster
- **Purpose**: Groups related signals for pattern analysis
- **Updated By**: `extract_tweets.py`

---

### 5. Telegram Bot Interface

**File**: `telegram_command_bot_improved.py`

**Bot Token**: `7790219276:AAHGWxUY9NqKvUuKNIrIkrmr3-YPG7L7JsY`

**Purpose**: Provides command-based control and receives real-time alerts

**Commands**:

- **`run kalshi sync`** - Fetches latest contracts from Kalshi API and updates WatchlistContracts
- **`check our x feed`** - Processes latest tweets, syncs follows, generates alerts
- **`status`** - Shows system status (alerts count, bot uptime, last check)
- **`debug`** - Displays detailed system diagnostics
- **`help`** - Lists all available commands

**Features**:
- **Enhanced logging** to `telegram_bot_debug.log`
- **Error handling** with user notifications
- **Timeout protection** for long-running commands
- **Consecutive error tracking** with auto-restart after 5 failures

**Process Management**:
- Runs as background process
- PID tracked for monitoring
- Auto-restarts on critical failures

---

## Data Flow

### Kalshi Sync Flow
```
User Command (Telegram)
    ↓
telegram_command_bot_improved.py
    ↓
kalshi_simple_fetcher.py
    ↓
Kalshi API (series-based queries)
    ↓
Filter contracts (price, expiration, keywords)
    ↓
Google Sheets (WatchlistContracts tab)
    ↓
Telegram notification (results summary)
```

### X Feed Processing Flow
```
User Command (Telegram)
    ↓
telegram_command_bot_improved.py
    ↓
extract_tweets.py
    ↓
sync_x_follows.py (auto-sync new follows)
    ↓
Extract tweets from X Following feed
    ↓
Load source weights from Google Sheets
    ↓
For each tweet:
    - Calculate sentiment & certainty
    - Match to contracts (similarity scoring)
    - Calculate SPS score
    - Check deduplication (6-hour window)
    ↓
If SPS ≥ 0.70:
    → Log to Alerts tab
    → Send Telegram alert
Else:
    → Log to No Action tab
    ↓
Telegram notification (processing summary)
```

---

## Key Files

### Core Scripts
- `kalshi_simple_fetcher.py` - Kalshi API integration with series-based querying
- `extract_tweets.py` - Tweet extraction and SPS scoring
- `sync_x_follows.py` - Auto-sync X follows to SourceWeights
- `telegram_command_bot_improved.py` - Telegram bot with enhanced logging
- `alerts_logger.py` - Google Sheets logging for alerts and signals

### Configuration Files
- `kalshi_private_key.pem` - Kalshi API authentication key
- `google_credentials.json` - Google Sheets API credentials
- `config.py` - System configuration (if exists)

### Memory/State Files
- `memory/signal_thresholds.json` - SPS threshold configuration
- `memory/contract_groups.json` - Contract categorization
- `memory/kalshibot_watchlist_memory.json` - Watchlist state

### Log Files
- `telegram_bot_debug.log` - Detailed bot operation logs
- `bot_output.log` - Bot stdout/stderr output

---

## Configuration

### Current Settings (Testing)

**Kalshi Filters**:
- Price Range: 0.05-0.95 (TESTING - WIDENED)
- Expiration: Within 150 days
- Keywords: 22 terms

**SPS Scoring**:
- Alert Threshold: 0.70
- Similarity Threshold: 0.70
- Deduplication Window: 6 hours

**New Follow Defaults**:
- Tier: 1
- Weight: 0.8

### Production Settings (Recommended)

**Kalshi Filters**:
- Price Range: 0.10-0.80 (10%-80% probability for tradeable uncertainty)
- Expiration: Within 60 days (focus on near-term events)
- Keywords: Same 22 terms

**SPS Scoring**:
- Keep current settings (0.70 threshold working well)

---

## Troubleshooting

### Common Issues

**1. Telegram Bot Not Responding**
- Check if process is running: `ps aux | grep telegram_command_bot`
- Check logs: `tail -50 telegram_bot_debug.log`
- Common cause: 409 Conflict (multiple instances)
- Solution: Clear webhook, kill old process, restart

**2. No Contracts Found in Kalshi Sync**
- Verify API authentication is working
- Check if series tickers are correct
- Confirm price range isn't too narrow
- Review expiration window (may need to extend)

**3. No Tweets Found in X Feed**
- Verify browser automation is working
- Check if X account is logged in
- Confirm follows are synced to SourceWeights

**4. Google Sheets Errors**
- Verify credentials file exists: `/home/ubuntu/google_credentials.json`
- Check sheet permissions for service account
- Confirm sheet ID is correct

### Debug Commands

```bash
# Check Telegram bot status
ps aux | grep telegram_command_bot

# View bot logs
tail -50 /home/ubuntu/kalshibot/telegram_bot_debug.log

# Test Kalshi API
cd /home/ubuntu/kalshibot && python3 kalshi_simple_fetcher.py

# Test X feed extraction
cd /home/ubuntu/kalshibot && python3 extract_tweets.py

# Restart Telegram bot
pkill -f telegram_command_bot
cd /home/ubuntu/kalshibot && python3 telegram_command_bot_improved.py > bot_output.log 2>&1 &
```

---

## System Requirements

### Dependencies
- Python 3.11+
- `requests` - HTTP requests
- `cryptography` - Kalshi API authentication
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` - Google Sheets
- `beautifulsoup4` - HTML parsing (for X feed)
- `selenium` or browser automation (for X feed extraction)

### External Services
- Kalshi API (authenticated)
- Google Sheets API (service account)
- Telegram Bot API
- X/Twitter (browser-based access via @poliseo84 account)

---

## Future Enhancements

### Potential Improvements
1. **Real-time monitoring** - Continuous feed processing instead of manual commands
2. **Automated trading** - Direct integration with Kalshi trading API
3. **Machine learning** - Improve SPS scoring with historical performance data
4. **Multi-source signals** - Add Reddit, news feeds, Discord, etc.
5. **Backtesting** - Validate SPS scoring against historical outcomes
6. **Portfolio management** - Track positions, P&L, risk exposure
7. **Advanced analytics** - Correlation analysis, signal clustering, pattern recognition

---

## Security Notes

### Credentials
- Kalshi API key stored in: `/home/ubuntu/kalshibot/kalshi_private_key.pem` (600 permissions)
- Google credentials in: `/home/ubuntu/google_credentials.json`
- Telegram bot token hardcoded in: `telegram_command_bot_improved.py`

### Best Practices
- Never commit credentials to version control
- Rotate API keys periodically
- Use environment variables for sensitive data
- Restrict Google Sheets service account permissions
- Monitor bot logs for unauthorized access attempts

---

## Contact & Support

**X Account**: @poliseo84
**Google Sheet**: https://docs.google.com/spreadsheets/d/1IAlJa5MnPVvQfi5-iTLdHS0ndUfgfjws1AeejdBGXj8

---

## Version History

**v1.0** (Feb 1, 2026)
- Initial system with Kalshi API integration
- X feed monitoring with SPS scoring
- Telegram bot interface
- Google Sheets database
- Series-based Kalshi querying (critical fix)
- Auto-sync X follows
- No Action tab for transparency
- Enhanced error handling and logging

---

## Appendix: Technical Details

### Kalshi API Price Format
- API returns prices as **integers (cents)**, not decimals
- Example: `yes_bid: 90` means 90¢ or $0.90
- **Must divide by 100** before comparing to price ranges

### Series-Based Querying Discovery
- Kalshi has thousands of markets, API returns max 1000 per query
- Political/economic contracts don't appear in first 1000 of general queries
- **Solution**: Query specific series with `series_ticker` parameter
- Example: `/markets?series_ticker=KXFEDDECISION&limit=200`

### SPS Scoring Example
```
Tweet: "BREAKING: Fed announces rate hold at March meeting"
Contract: "Will Fed maintain rates at March 2026 meeting?"

Source Weight: 1.0 (Tier 1 source like @Reuters)
Sentiment: 0.7 (positive/breaking news)
Certainty: 1.0 (definitive announcement)
Similarity: 0.95 (high semantic match)

SPS = 1.0 × (0.7 + 1.0) × 0.95 = 1.615

Since 1.615 > 0.70 threshold → ALERT GENERATED
```

---

End of Documentation
