# VantaStonk Setup Guide

## Prerequisites

- Python 3.11+
- Telegram account
- Internet connection for API access

## Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/montgomerycj/VantaStonk.git
   cd VantaStonk
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Telegram Bot**
   - Message @BotFather on Telegram
   - Create new bot: `/newbot`
   - Get bot token
   - Get your chat ID (message @userinfobot)

4. **Update Configuration**
   Edit `main.py` lines 59-60:
   ```python
   self.telegram_bot_token = "YOUR_BOT_TOKEN"
   self.telegram_chat_id = "YOUR_CHAT_ID"
   ```

5. **Run Agent**
   ```bash
   python main.py
   ```

## Webhook Setup (for production)

1. **Deploy to server** (Heroku, AWS, etc.)
2. **Set webhook URL**:
   ```bash
   curl -X POST "https://api.telegram.org/botYOUR_TOKEN/setWebhook" \
   -H "Content-Type: application/json" \
   -d '{"url": "https://your-domain.com/webhook"}'
   ```

## Memory Persistence

Agent stores data in `vantastonk_memory.json`:
- Watchlist tickers
- Price thresholds  
- Trading positions
- Glance history
- ShadowList tracking

## Commands

Send these via Telegram:
- `help` - Command list
- `add AAPL to watchlist` - Monitor AAPL
- `set AAPL threshold at 5` - 5% alert
- `show watchlist` - View monitored stocks
- `status` - Agent health

## Troubleshooting

- **No responses**: Check bot token and chat ID
- **Memory lost**: Ensure persistent storage location
- **API errors**: Verify internet connection

