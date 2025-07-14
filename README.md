
# VantaStonk 💹  
**Agentic Trading Assistant (Built with Manus, Claude, and Telegram)**  
_Designed for real-time alpha discovery using the 95v2 framework._

---

## 🚀 Overview

**VantaStonk** is a self-monitoring, autonomous trading assistant that uses LLM reasoning, custom memory, and real-time data to identify tactical stock trading opportunities. Built with the Manus agent platform and integrated with Yahoo Finance + Telegram, it proactively alerts the user to actionable setups based on a customized strategy called **95v2**.

The agent tracks watchlisted tickers, applies trigger thresholds, executes daily strategy scans, and communicates via Telegram — all without requiring live user input.

---

## ⚙️ Core Features

- 🕵️ **ShadowList**: Maintains a rolling list of tickers likely to be targeted by AI/quant funds  
- 📊 **Glance**: Daily tactical scan generating:
  - Momentum trade
  - Pair trade
  - Macro tilt
  - Optional hedge  
- 📉 **Threshold Alerts**: Real-time price monitoring via Yahoo Finance triggers Telegram alerts
- 💬 **Telegram Bot**: Receives commands, delivers alerts, and provides summaries
- 🧠 **Persistent Memory**: Tracks positions (`myStonks`), Glance logs, alert logs, and logic state

---

## 🧠 Strategy: The 95v2 Framework

VantaStonk uses a disciplined trade setup strategy with five pillars:

1. **Momentum** — Finds strong relative movers, avoids >5% past run-ups
2. **Pair Trades** — Based on valuation/sentiment divergence
3. **Macro Tilt** — Driven by geopolitical or policy catalysts
4. **Defensive Hedge** — Optional short/volatility idea if markets overextended
5. **ShadowList Scanning** — Predicts future algorithmic inflows

---

## 🧱 Tech Stack

| Component | Description |
|----------|-------------|
| **Manus.ai** | Agent orchestration, scheduling, and memory |
| **Claude 3 Haiku / GPT-4o** | Core logic and Glance reasoning |
| **Yahoo Finance API (unofficial)** | Price + open data for tickers |
| **Telegram Bot API** | Alert delivery and command interface |
| **Memory Model** | JSON-based persistent state for tickers, logic, and logs |

---

## 📚 Key Memory Variables

| Variable | Purpose |
|---------|---------|
| `myStonks` | Current user-held tickers |
| `watchlist` | Tickers being monitored |
| `thresholds` | % drop levels that trigger alerts |
| `shadowListLog` | Tickers flagged for quant/AI watch |
| `glanceIdeas` | Historical Glance reports |
| `lastGlanceDate` | Date of last Glance run |
| `alertLog` | Tracks which tickers were already alerted on today |

---

## 💬 Telegram Integration

To configure:
1. Create bot via `@BotFather` in Telegram
2. Paste token into Manus tool
3. Use `sendTelegramAlert` tool to ping your `chat_id`
4. Commands supported:
   - `Add PYPL to watchlist`
   - `Set threshold for RPD at -5`
   - `Run Glance now`
   - `Show ShadowList`

---

## 🛠️ File Structure (if exported locally)

```
VantaStonk/
├── README.md
├── prompts/
│   └── glance_prompt.txt
├── logic/
│   ├── scheduler_logic.md
│   └── alert_logic.md
├── tools/
│   ├── getYahooPriceData.json
│   └── sendTelegramAlert.json
├── memory/
│   └── initial_memory.json
└── manifest.txt
```

---

## 🗺️ Roadmap

- [ ] Add trade journaling tool
- [ ] Enable multi-watchlist profiles (e.g., ShadowList vs Active)
- [ ] Telegram inline command shortcuts (e.g., `/glance`)
- [ ] Performance dashboard (Glance hit rate)
- [ ] Cursor/VS Code local backend version

---

## 👥 Contributors

- **CJ Montgomery** — Project founder, strategic lead  
- Future collaborators: _add your GitHub username here_

---

## 📜 License

This is a private experimental repo. License TBD upon stabilization.
