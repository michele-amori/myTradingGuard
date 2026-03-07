# ⚡ MyTradingGuard

MyTradingGuard is a trading discipline tool for macOS. It sits between TradingView Desktop and your Tradovate broker account and **automatically blocks orders** whenever your personal rules are violated — for example, if you're trading outside your allowed hours, you've already hit your daily loss limit, or your order size is too large.

---

## What you need

- A Mac running **macOS Sequoia (15)** or later
- **TradingView Desktop** installed (the standalone Mac app, not the browser)
- A **Tradovate** account (live or demo)
- Basic comfort opening Terminal and running a command

You do **not** need to know how to code.

---

## How it works

```
TradingView  →  MyTradingGuard (proxy)  →  Tradovate
```

MyTradingGuard runs a local proxy in the background. TradingView is configured to send its traffic through that proxy. Every time you click "Buy" or "Sell", MyTradingGuard checks your rules first. If a rule is violated, the order is stopped before it ever reaches Tradovate.

A native macOS app shows you the live status of all your rules in real time.

---

## Installation

### Step 1 — Download

Download or clone this repository and place the folder wherever you like, for example your Desktop.

### Step 2 — Install Python dependencies

Open **Terminal** (you can find it in Applications → Utilities) and run:

```bash
cd ~/Desktop/MyTradingGuard
pip3 install -r requirements.txt
```

If you see a permissions error, run this instead:

```bash
pip3 install -r requirements.txt --break-system-packages
```

### Step 3 — One-time macOS setup

Still in Terminal, run:

```bash
bash setup_macos.sh
```

This script does two things:
1. Generates a local SSL certificate so the proxy can inspect HTTPS traffic
2. Installs that certificate on your Mac as trusted (you'll be asked for your Mac password)

> **Why is this needed?** TradingView communicates with Tradovate over encrypted HTTPS. The proxy needs to read those messages to enforce your rules. The certificate stays on your Mac and is never transmitted anywhere.

> **If macOS blocks the script:** go to System Settings → Privacy & Security and click "Allow Anyway".

### Step 4 — Install the app

Build and install the native macOS app by running:

```bash
bash MyTradingGuardUI/build_dmg.sh
```

This creates a file called `MyTradingGuard.dmg` in the project folder. Open it and drag **MyTradingGuard.app** into the **Applications** folder, exactly like any other Mac app.

---

## Daily use

### Starting MyTradingGuard

Every trading day, open Terminal and run:

```bash
cd ~/Desktop/MyTradingGuard
bash start.sh
```

This starts the proxy in the background and opens TradingView Desktop with the proxy active. A terminal window will remain open — **do not close it** while you are trading.

Then open **MyTradingGuard** from your Applications folder. The app shows the live status of all your rules and a log of recent events.

### Stopping MyTradingGuard

When you are done trading, run:

```bash
bash teardown_macos.sh
```

This stops the proxy and closes TradingView. Your Mac's internet connection returns to normal.

> **Important:** always run `teardown_macos.sh` when you finish. If you close Terminal without running it, the proxy may keep running in the background.

---

## Configuring your rules

Open the file `config.json` with any text editor (TextEdit works fine). Each rule has an `"active"` flag — set it to `true` to enable the rule or `false` to disable it without losing the value.

```json
{
  "rules": {

    "time_window": {
      "active": true,
      "timezone": "America/New_York",
      "windows": [
        { "start": "09:33", "end": "10:15" },
        { "start": "10:42", "end": "11:15" }
      ]
    },

    "cooldown": {
      "active": true,
      "minutes": 30
    },

    "max_daily_trades": {
      "active": true,
      "value": 3
    },

    "max_daily_losses": {
      "active": true,
      "value": 2
    },

    "max_order_size": {
      "active": true,
      "value": 2
    }

  },

  "broker": "tradovate",
  "broker_env": "demo"
}
```

| Rule | What it does |
|------|--------------|
| `time_window` | Allows trading only during the specified time windows. Orders outside those hours are blocked. |
| `cooldown` | Forces a mandatory waiting period after each trade. |
| `max_daily_trades` | Blocks all orders once you have reached the daily trade limit. |
| `max_daily_losses` | Blocks all orders once you have hit the maximum number of losing trades for the day. |
| `max_order_size` | Blocks any single order whose size exceeds the maximum number of contracts. |

**Changes to `config.json` take effect immediately** — no restart needed.

---

## The rules in detail

**`max_daily_trades` takes priority over `max_daily_losses`.** For example, if your limit is 3 trades and 4 losses, and you have already placed 3 trades (all losses), the next order will be blocked because of the trade limit — not the loss limit.

**`max_order_size` is checked per order.** It does not block trading entirely — it only blocks individual orders that are too large.

---

## Switching between demo and live

In `config.json`, change:

```json
"broker_env": "demo"
```

to:

```json
"broker_env": "live"
```

---

## Troubleshooting

**TradingView says "Failed to fetch" when I place an order**
This is the expected message when MyTradingGuard blocks an order. Check the app or the terminal to see which rule was triggered.

**TradingView cannot connect to Tradovate**
Make sure `bash start.sh` is running before you open TradingView. If the problem persists, run `bash teardown_macos.sh`, restart your Mac, and try again.

**SSL certificate error in TradingView**
Open Keychain Access (Applications → Utilities → Keychain Access), go to the System keychain, search for "mitmproxy", double-click the certificate and set it to **Always Trust**.

**My internet stops working after closing Terminal**
Run `bash teardown_macos.sh` to restore your network settings, or go to System Settings → Network → your Wi-Fi → Details → Proxies and uncheck all proxy entries.

**The app shows "Waiting for MyTradingGuard to start…"**
The native app reads its data from the proxy. Start `bash start.sh` first, then open the app.

---

## Project structure

```
MyTradingGuard/
├── start.sh              ← Run this every trading day
├── teardown_macos.sh     ← Run this when done
├── setup_macos.sh        ← Run once at first install
├── config.json           ← Your rules (edit this)
├── requirements.txt      ← Python dependencies
│
├── main.py               ← Proxy entry point
├── proxy_addon.py        ← Order interception logic
├── rules_engine.py       ← Rule evaluation
├── trade_state.py        ← Daily trade counters
├── config.py             ← Config loader
├── notifier.py           ← Sound alerts
├── tradovate_client.py   ← Tradovate REST client
├── ui_state_writer.py    ← Feeds data to the macOS app
│
└── MyTradingGuardUI/     ← Native macOS app (SwiftUI)
    ├── build_dmg.sh      ← Builds the installable .dmg
    └── Sources/
```

---

## Running the tests

To verify everything is working correctly without TradingView or live markets:

```bash
python3 test_runner.py
```

All 33 tests should pass.
