#!/bin/bash
# ============================================================
#  MyTradingGuard — Teardown
#  Ferma il proxy e chiude TradingView.
#  Il proxy di sistema NON viene toccato.
# ============================================================

echo ""
echo "→ Chiusura MyTradingGuard..."
pkill -f "main.py" 2>/dev/null && echo "   ✓ Proxy fermato" || echo "   • Proxy non in esecuzione"
pkill -f "TradingView" 2>/dev/null && echo "   ✓ TradingView chiuso" || echo "   • TradingView non in esecuzione"
echo ""
echo "✓ MyTradingGuard arrestato."
echo ""
