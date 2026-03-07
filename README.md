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

The script handles TradingView automatically:

| Situation | What happens |
|-----------|--------------|
| TradingView is **not open** | It is launched automatically with the proxy active |
| TradingView is **already open with the proxy** | Nothing changes — MyTradingGuard connects to it as-is |
| TradingView is **open but without the proxy** | It is closed and relaunched with the proxy active |

A terminal window will remain open — **do not close it** while you are trading.

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

---

## File reference

This section explains what every file in the project does and how the files interact with each other.

### Overview of the data flow

```
config.json
    │
    └─► config.py ──────────────────────────────────────┐
                                                         │
start.sh ──► main.py ──► proxy_addon.py ◄──────────────►│
                │              │                         │
                │         rules_engine.py ◄──────────────┤
                │              │                         │
                │         trade_state.py ◄───────────────┤
                │              │                         │
                │         tradovate_client.py            │
                │              │                         │
                │         notifier.py                    │
                │                                        │
                └─► ui_state_writer.py ──► ~/.mytradingguard/ui_state.json
                                                         │
                                         MyTradingGuardUI.app (Swift)
```

---

### `start.sh` — daily launcher

The only file you need to run every day. It does three things in sequence:

1. Starts the Python proxy (`main.py`) in the background
2. Waits 2 seconds for the proxy to be ready
3. Handles TradingView: launches it if it is not running, does nothing if it is already running with the proxy, or restarts it with the proxy if it is running without one

**Interacts with:** `main.py` (spawns it), `teardown_macos.sh` (the complement to stop everything)

---

### `main.py` — entry point

The main Python process. It is started by `start.sh` and keeps running for the entire trading session.

On startup it:
- Loads `config.json` via `config.py`
- Creates the `TradeState` and `RulesEngine` objects
- Starts the `UIStateWriter` background thread
- Starts the mitmproxy proxy in a separate thread, attaching `proxy_addon.py` as its addon
- Renders a live terminal dashboard that refreshes every second

The terminal dashboard is a secondary, raw interface — the native macOS app (`MyTradingGuardUI.app`) is the primary one.

**Interacts with:** `config.py`, `trade_state.py`, `rules_engine.py`, `ui_state_writer.py`, `proxy_addon.py`

---

### `config.py` — configuration loader

Reads `config.json` and converts it into typed Python objects. Each rule is represented by its own dataclass (`TimeWindowRule`, `CooldownRule`, `MaxDailyTradesRule`, `MaxDailyLossesRule`, `MaxOrderSizeRule`), all grouped under a top-level `Config` object.

Key design decisions:
- Every rule has an `active` boolean. If `False`, the rule is skipped entirely without needing to remove it from the config file.
- The `reload()` method allows hot-reloading the configuration at runtime: `proxy_addon.py` calls it on every incoming order, so changes to `config.json` take effect immediately without restarting anything.
- On load, the config is validated: malformed time windows raise an error, unsupported broker names raise an error.

**Read by:** `main.py`, `proxy_addon.py`, `rules_engine.py`, `ui_state_writer.py`, `test_runner.py`
**Reads:** `config.json`

---

### `rules_engine.py` — rule evaluation

A stateless class that evaluates each rule against the current state and configuration. Every method returns a `(bool, str)` tuple: `True` if the order is allowed, `False` plus a human-readable reason if it is blocked.

Rules and their evaluation order:

| Priority | Rule | What is checked |
|----------|------|-----------------|
| 1 | `check_time_window` | Is the current time inside one of the allowed windows? |
| 2 | `check_cooldown` | Has enough time passed since the last trade? |
| 3 | `check_max_trades` | Is the daily trade count below the limit? |
| 4 | `check_max_losses` | Is the daily loss count below the limit? |
| — | `check_order_size` | Is the order quantity within the allowed size? (checked separately, needs the qty from the request body) |

`check_all()` runs rules 1–4 in order and stops at the first failure. This means if both the trade limit and the loss limit are exceeded, the trade limit message is shown — not the loss limit.

If a rule's `active` flag is `False`, its method returns `(True, "")` immediately without checking anything.

**Used by:** `proxy_addon.py`, `ui_state_writer.py`, `main.py`, `test_runner.py`
**Uses:** `trade_state.py` (read-only), `config.py` (read-only)

---

### `trade_state.py` — daily counters

Manages and persists the in-session trading state: daily trade count, daily loss count, the timestamp of the last trade, and an in-memory log of recent events.

Key behaviour:
- **Thread-safe:** all reads and writes go through a `threading.Lock`.
- **Daily reset:** `_ensure_today()` is called before every read or write. If the stored date does not match today, all counters are silently reset to zero. This means the state resets automatically at midnight with no manual intervention needed.
- **Persistence:** the state is saved to `~/.mytradingguard/state.json` after every change, so it survives a proxy restart within the same day.
- **`sync_from_api()`:** called by `proxy_addon.py` after the Tradovate API is queried at startup. It overwrites the local counters only if the API values are higher — never lower — to avoid overwriting state with stale data if the API call is delayed.
- **Event log:** the last 50 events (BLOCKED, PASSED, LOSS, WIN) are kept in memory and exposed as a list for the terminal dashboard and the native app.

**Written by:** `proxy_addon.py` (records trades, losses, blocks), `tradovate_client.py` (via `sync_from_api`)
**Read by:** `rules_engine.py`, `ui_state_writer.py`, `main.py`
**Persists to:** `~/.mytradingguard/state.json`

---

### `proxy_addon.py` — order interception

The core of the system. This is a mitmproxy addon — a class that mitmproxy calls on every HTTP request and response passing through the proxy.

**On every request (`request` hook):**
1. If the request is going to any broker host, it tries to extract the account ID and Bearer token from it and passes them to `tradovate_client.py`.
2. If the request is an order (POST to a recognised order endpoint with the expected body parameters), it calls `config.py`'s hot-reload, runs `rules_engine.py`'s `check_all()`, then checks the order size. If any check fails, the request is immediately blocked by replacing it with a `403 JSON` response — the request never reaches Tradovate.

**On every response (`response` hook):**
1. If the response is for a successful order (status 200/201 containing `orderId`), it calls `trade_state.py`'s `record_trade()`.
2. If the response is a positions snapshot, it compares it to the previous snapshot to detect trades that just closed at a loss (`soldValue - boughtValue < 0`), and calls `record_loss()` accordingly. This is a passive fallback mechanism for loss detection.

**Credential capture** works passively: `proxy_addon.py` reads the `Authorization: Bearer …` header and the `/accounts/{id}/` path from every broker request. The first time it captures a valid pair, it calls `tradovate_client.py`'s `capture()`, which fires the `_on_credentials_ready` callback. This callback fetches the real daily history from Tradovate and calls `trade_state.py`'s `sync_from_api()` to correct the local counters.

**Interacts with:** `config.py` (hot-reload), `rules_engine.py` (evaluates rules), `trade_state.py` (records outcomes), `tradovate_client.py` (credential capture and API sync), `notifier.py` (sound alerts)

---

### `tradovate_client.py` — Tradovate REST client

Makes authenticated HTTP requests to the Tradovate REST API to fetch the real daily trading history. It does not store credentials in any file — it receives them from `proxy_addon.py` each time TradingView makes an authenticated request.

The main method, `fetch_daily_losses_and_trades()`, calls `/position/ldeps?masterids={accountId}` and returns two numbers: how many trades closed today and how many of those were losses. It filters out positions from previous days and positions that are still open.

The `capture(account_id, token)` method stores the credentials and fires the `on_ready` callback the first time a valid pair is received. Subsequent calls update the credentials silently (in case the token is refreshed during the session).

Supports both `live` and `demo` environments, pointing to their respective base URLs.

**Called by:** `proxy_addon.py`
**Calls:** Tradovate REST API (`/position/ldeps`)
**Provides data to:** `trade_state.py` (via `sync_from_api`)

---

### `notifier.py` — sound alerts

A minimal class that plays macOS system sounds via `afplay` when an order is blocked or allowed. Runs asynchronously in a daemon thread so it never blocks the proxy.

Two sounds are used:
- `Basso.aiff` — played when an order is blocked
- `Funk.aiff` — played when an order is allowed (only if `notify_allowed: true` in `config.json`)

Both `sound_enabled` and `notify_allowed` are read from `config.json` at startup.

**Called by:** `proxy_addon.py`

---

### `ui_state_writer.py` — bridge between Python and the macOS app

Runs as a background thread inside `main.py`. Every second it evaluates the current state of all rules, formats the results, and writes a JSON snapshot to `~/.mytradingguard/ui_state.json`.

The write is atomic: the data is first written to a `.tmp` file, then renamed over the real file. This guarantees the native macOS app never reads a half-written file.

The JSON contains everything the native app needs: the current timestamp, global block status, per-rule status (name, active, ok, detail, optional progress bar values), and the last 20 events.

**Reads from:** `trade_state.py`, `rules_engine.py`, `config.py`
**Writes to:** `~/.mytradingguard/ui_state.json`
**Read by:** `MyTradingGuardUI.app`

---

### `MyTradingGuardUI/` — native macOS app (SwiftUI)

A native macOS application written in Swift and SwiftUI. It reads `~/.mytradingguard/ui_state.json` every second using a `Timer` and displays the data in a window with three zones:

- **Header:** current time and a global TRADING ENABLED / TRADING BLOCKED badge
- **Left panel:** the five rules with their current status (green check, red X, or grey dash if disabled), detail text, and progress bars for count-based rules
- **Right panel:** the event log with colour-coded icons for BLOCKED, PASSED, LOSS, and WIN events
- **Footer:** proxy port, broker and environment, daily trade and loss counts

The app is entirely passive — it only reads the JSON file and never writes to it or communicates with the proxy in any other way.

| File | Role |
|------|------|
| `Sources/MyTradingGuardUI/App.swift` | `@main` entry point, window configuration |
| `Sources/MyTradingGuardUI/StatusModel.swift` | `ObservableObject` that loads and decodes the JSON every second |
| `Sources/MyTradingGuardUI/ContentView.swift` | All SwiftUI views: header, rules panel, events panel, footer |
| `Package.swift` | Swift Package Manager manifest (requires macOS 14+) |
| `build_dmg.sh` | Build script: compiles Swift, generates the app icon, assembles the `.app` bundle, and creates an installable `.dmg` |
| `make_icon.swift` | Standalone Swift script that generates the app icon PNG using AppKit |

**Reads from:** `~/.mytradingguard/ui_state.json` (written by `ui_state_writer.py`)

---

### `test_runner.py` — offline test suite

Runs 33 automated tests that cover the entire system without requiring TradingView, Tradovate, or live markets. Tests use a temporary state file instead of the real `~/.mytradingguard/state.json`, so they never interfere with a live session.

Test sections:

| Section | What is tested |
|---------|---------------|
| Rules Engine (16 tests) | Each rule individually (allowed, blocked, active=False bypass), plus rule priority |
| TradeState (3 tests) | `sync_from_api` with higher and lower values, `record_loss` |
| TradovateClient (5 tests) | Mock HTTP server returning fake positions, credential capture, `on_ready` callback |
| Proxy credential capture (4 tests) | `accountId` and token extraction from a fake mitmproxy flow |
| Integration (5 tests) | Full allow/block scenarios end to end |

**Tests:** `rules_engine.py`, `trade_state.py`, `tradovate_client.py`, `proxy_addon.py`

---

### Support files

| File | Purpose |
|------|---------|
| `config.json` | Your personal rules configuration. The only file you are expected to edit. |
| `requirements.txt` | Python dependencies: `mitmproxy`, `rich`, `pytz`. Install with `pip3 install -r requirements.txt`. |
| `setup_macos.sh` | One-time setup: generates the mitmproxy SSL certificate and installs it as trusted on your Mac. |
| `teardown_macos.sh` | Stops the proxy and TradingView, restores normal network settings. |
| `debug_proxy.py` | Developer tool: logs all proxied HTTP traffic to the console for inspection. |
| `debug_state.py` | Developer tool: captures and prints the raw JSON response from the Tradovate `/state` endpoint. |
| `~/.mytradingguard/state.json` | Daily state file (auto-created). Stores trade count, loss count, and last trade time. Resets at midnight. |
| `~/.mytradingguard/ui_state.json` | Real-time snapshot (auto-created, updated every second). Consumed by the native app. |
