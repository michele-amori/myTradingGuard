#!/bin/bash
# ============================================================
#  MyTradingGuard — Avvio
#  1. Avvia il proxy mitmproxy (MyTradingGuard)
#  2. Apre TradingView Desktop puntandolo al proxy locale
#     SOLO TradingView passa dal proxy — il resto di macOS
#     non viene toccato.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
TRADINGVIEW="/Applications/TradingView.app/Contents/MacOS/TradingView"
PROXY_PORT=8080

echo ""
echo "⚡ MyTradingGuard — avvio..."
echo ""

# ── 1. Avvia il proxy in background ─────────────────────────
cd "$SCRIPT_DIR"
"$PYTHON" main.py &
PROXY_PID=$!
echo "→ Proxy avviato (PID $PROXY_PID) su localhost:$PROXY_PORT"

# Aspetta che il proxy sia pronto
sleep 2

# ── 2. Apri TradingView con il proxy locale ──────────────────
echo "→ Apertura TradingView con proxy MyTradingGuard..."
"$TRADINGVIEW" \
    --proxy-server="127.0.0.1:$PROXY_PORT" \
    --ignore-certificate-errors \
    &>/dev/null &

echo "→ TradingView avviato"
echo ""
echo "✓ Tutto pronto. Chiudi questa finestra per fermare il proxy."
echo "  (oppure premi Ctrl+C)"
echo ""

# ── 3. Aspetta — quando esci da qui il proxy si ferma ────────
wait $PROXY_PID
