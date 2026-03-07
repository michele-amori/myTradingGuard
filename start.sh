#!/bin/bash
# ============================================================
#  MyTradingGuard — Start
#
#  1. Starts the mitmproxy proxy (MyTradingGuard)
#  2. Handles TradingView Desktop:
#       - Not running       → launch it with the proxy
#       - Running + proxy   → connect to it as-is
#       - Running, no proxy → quit and relaunch with proxy
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
TRADINGVIEW="/Applications/TradingView.app/Contents/MacOS/TradingView"
PROXY_PORT=8080

echo ""
echo "⚡ MyTradingGuard — starting..."
echo ""

# ── 1. Start the proxy in background ────────────────────────
cd "$SCRIPT_DIR"
"$PYTHON" main.py &
PROXY_PID=$!
echo "→ Proxy started (PID $PROXY_PID) on localhost:$PROXY_PORT"

# Wait for the proxy to be ready
sleep 2

# ── 2. Handle TradingView ────────────────────────────────────
_launch_tradingview() {
    "$TRADINGVIEW" \
        --proxy-server="127.0.0.1:$PROXY_PORT" \
        --ignore-certificate-errors \
        &>/dev/null &
}

if pgrep -x "TradingView" > /dev/null 2>&1; then
    # TradingView is running — check if it was launched with the proxy
    if ps aux | grep -v grep | grep "TradingView" | grep -q "proxy-server"; then
        echo "→ TradingView already running with MyTradingGuard proxy ✓"
    else
        echo "→ TradingView is running without proxy — restarting it..."
        # Quit gracefully first, then force-kill if needed after 5 seconds
        osascript -e 'quit app "TradingView"' 2>/dev/null || true
        for i in $(seq 1 5); do
            sleep 1
            pgrep -x "TradingView" > /dev/null 2>&1 || break
        done
        # Force kill if still running
        pkill -x "TradingView" 2>/dev/null || true
        sleep 1
        _launch_tradingview
        echo "→ TradingView restarted with proxy"
    fi
else
    echo "→ TradingView not running — launching with proxy..."
    _launch_tradingview
    echo "→ TradingView launched"
fi

echo ""
echo "✓ Ready. Close this window to stop the proxy."
echo "  (or press Ctrl+C)"
echo ""

# ── 3. Keep running — proxy stops when this script exits ────
wait $PROXY_PID
