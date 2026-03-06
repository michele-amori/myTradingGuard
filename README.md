# ⚡ MyTradingGuard

A trading discipline tool for TradingView Desktop on macOS.
Blocks orders from reaching the broker when your configured rules are not met.

## How it works

```
TradingView App ──► [Local Proxy :8080] ──► Tradovate API
                             │
                       Checks rules:
                       • Time window  ✓/✗
                       • Cooldown     ✓/✗
                       • Max daily trades ✓/✗
```

The proxy intercepts HTTP requests that TradingView Desktop sends to Tradovate.
If any rule is violated, the request is blocked **before** it reaches the broker — the order never goes through.

---

## Installation (one-time setup)

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Run the macOS setup script

```bash
bash setup_macos.sh
```

This script:
- Generates the mitmproxy SSL certificate
- Installs it in the System Keychain as **trusted** (requires admin password)

> ⚠️ The certificate is required to intercept HTTPS traffic.
> It is generated locally on your Mac and never transmitted anywhere.

---

## Configuration

Edit `config.json` to define your rules:

```json
{
  "time_windows": [
    { "start": "09:30", "end": "11:30" },
    { "start": "14:00", "end": "16:00" }
  ],
  "timezone": "America/New_York",
  "cooldown_minutes": 5,
  "max_daily_trades": 3,
  "broker": "tradovate",
  "broker_env": "live",
  "proxy_port": 8080
}
```

| Field | Description |
|-------|-------------|
| `time_windows` | Time ranges during which trading is **allowed**. Orders outside these windows are blocked. |
| `timezone` | Timezone for the time windows (e.g. `America/New_York`, `Europe/Rome`) |
| `cooldown_minutes` | Mandatory wait time after each trade. `0` = disabled |
| `max_daily_trades` | Maximum number of orders per day. `0` = disabled |
| `broker` | `tradovate` or `interactive_brokers` |
| `broker_env` | `live` or `demo` |

**Configuration is reloaded automatically** whenever you save the file — no restart needed.

---

## Daily usage

```bash
bash start.sh
```

This launches the proxy and opens TradingView Desktop with the proxy active. A live dashboard is shown in the terminal:

```
╔══════════════════════════════════╗
║       ⚡ MyTradingGuard          ║
║  Friday 06 Mar 2026  10:42:33    ║
╚══════════════════════════════════╝

┌─ Active Rules ───────────────────────────────┐
│ 🟢  Time Window       09:30–11:30 ✓          │
│ 🔴  Cooldown (5min)   Unlocks in 3m 12s      │
│ 🟢  Max Daily Trades  ████░░░░░░  2/3        │
└──────────────────────────────────────────────┘

         🚫  TRADING BLOCKED

┌─ Recent Events ──────────────────────────────┐
│ 10:41:15  🔴 BLOCKED  Cooldown active: ...   │
│ 10:38:02  🟢 PASSED   LONG NQ                │
└──────────────────────────────────────────────┘
```

Press `Ctrl+C` to stop the proxy and exit.

---

## Stopping the proxy

```bash
bash teardown_macos.sh
```

Kills the proxy process and closes TradingView.

---

## Project structure

```
mytradingguard/
├── main.py           # Entry point + terminal dashboard
├── proxy_addon.py    # mitmproxy addon — intercepts orders
├── rules_engine.py   # Rules evaluation logic
├── trade_state.py    # Daily state (persisted to disk)
├── config.py         # Configuration loader
├── config.json       # ← Edit your rules here
├── notifier.py       # Sound alerts on block/allow
├── start.sh          # Daily launcher
├── setup_macos.sh    # One-time macOS setup
├── teardown_macos.sh # Stop proxy
├── debug_proxy.py    # Debug tool — logs all Tradovate traffic
└── requirements.txt
```

---

## Adding a new broker

Edit `BROKER_PATTERNS` in `proxy_addon.py`:

```python
"my_broker": {
    "hosts": ["api.mybroker.com"],
    "order_paths": [r"/v1/orders", r"/api/place"],
    "order_body_params": ["symbol", "side", "qty"],
    "success_field": "order_id",
},
```

---

## Troubleshooting

**TradingView does not connect after setup**
→ Make sure `bash start.sh` is running before opening TradingView.

**SSL certificate error**
→ Open Keychain Access → System → search "mitmproxy" → double-click → Always Trust.

**Proxy blocks non-broker traffic**
→ This is expected: mitmproxy handles all traffic, but MyTradingGuard only intercepts broker order endpoints. Everything else passes through untouched.
