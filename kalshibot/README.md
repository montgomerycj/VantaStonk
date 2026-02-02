# Kalshibot

AI-powered trading assistant for Kalshi prediction markets.

## Overview

Kalshibot monitors social media signals (Twitter/X), matches them with relevant Kalshi contracts, and generates trading alerts based on sentiment, certainty, and source credibility scoring.

## Quick Start

### Prerequisites
- Python 3.11+
- Kalshi API credentials
- Google Sheets API credentials
- Telegram Bot token
- X/Twitter account access

### Installation

```bash
pip3 install requests cryptography google-auth google-auth-oauthlib google-api-python-client
```

### Configuration

1. **Kalshi API**: Place your private key in `kalshi_private_key.pem`
2. **Google Sheets**: Place service account credentials in `google_credentials.json`
3. **Telegram Bot**: Update bot token in `telegram_command_bot_improved.py`

### Running

```bash
# Start Telegram bot
python3 telegram_command_bot_improved.py

# Manual sync
python3 kalshi_simple_fetcher.py

# Process X feed
python3 extract_tweets.py
```

## Telegram Commands

- `run kalshi sync` - Fetch latest contracts from Kalshi
- `check our x feed` - Process tweets and generate alerts
- `status` - Show system status
- `debug` - Display diagnostics
- `help` - List all commands

## Documentation

See `kalshibot_system_documentation.md` for complete system documentation.

## Security

**Never commit sensitive files:**
- `kalshi_private_key.pem`
- `google_credentials.json`
- `*.log` files

These are excluded via `.gitignore`.

## Components

- **kalshi_simple_fetcher.py** - Kalshi API integration
- **extract_tweets.py** - X feed monitoring and SPS scoring
- **sync_x_follows.py** - Auto-sync X follows to source weights
- **telegram_command_bot_improved.py** - Telegram bot interface
- **alerts_logger.py** - Google Sheets logging

## License

Private project - All rights reserved
