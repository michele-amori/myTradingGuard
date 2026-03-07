#!/bin/bash
# ============================================================
#  MyTradingGuard — Setup macOS
#  Installa il certificato mitmproxy e configura il proxy di
#  sistema per intercettare il traffico di TradingView.
#
#  Esegui UNA SOLA VOLTA, poi usa `python3 main.py` ogni volta.
# ============================================================

set -e

PROXY_PORT=8080
CERT_PATH="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
SERVICE="Wi-Fi"   # Cambia in "Ethernet" se usi cavo

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       MyTradingGuard — macOS Setup       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Fix certificati Python su macOS ──────────────────────────────
echo "→ Fix certificati SSL di Python..."
# Cerca Install Certificates.command per tutte le versioni di Python installate
CERT_CMD=$(find /Applications/Python* -name "Install Certificates.command" 2>/dev/null | head -1)
if [ -n "$CERT_CMD" ]; then
    bash "$CERT_CMD" > /dev/null 2>&1
    echo "   ✓ Certificati Python aggiornati"
else
    # Fallback: installa certifi e punta Python ad esso
    pip3 install --upgrade certifi --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>/dev/null | tail -2
    CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null)
    if [ -n "$CERT_FILE" ]; then
        export SSL_CERT_FILE="$CERT_FILE"
        export REQUESTS_CA_BUNDLE="$CERT_FILE"
        echo "   ✓ Certificati via certifi: $CERT_FILE"
    fi
fi

# ── 2. Controlla dipendenze ─────────────────────────────────────────
echo ""
echo "→ Verifica dipendenze Python..."
if ! python3 -c "import mitmproxy" 2>/dev/null; then
    echo "   mitmproxy non trovato. Installazione in corso..."
    pip3 install mitmproxy rich pytz \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        --break-system-packages 2>&1 | tail -5
    if ! python3 -c "import mitmproxy" 2>/dev/null; then
        echo "   ✗ Installazione fallita. Prova manualmente:"
        echo "     pip3 install mitmproxy rich pytz --trusted-host pypi.org --trusted-host files.pythonhosted.org"
        exit 1
    fi
    echo "   ✓ mitmproxy installato"
else
    echo "   ✓ mitmproxy trovato"
fi

# ── 3. Genera certificato mitmproxy ─────────────────────────────────
echo ""
echo "→ Generazione certificato mitmproxy..."
if [ ! -f "$CERT_PATH" ]; then
    echo "   Avvio mitmproxy per 3 secondi per generare i certificati..."
    # Avvia mitmdump in background, aspetta che generi i cert, poi killalo
    mitmdump --listen-port 18999 --quiet &
    MITM_PID=$!
    sleep 3
    kill $MITM_PID 2>/dev/null
    wait $MITM_PID 2>/dev/null
fi

if [ -f "$CERT_PATH" ]; then
    echo "   ✓ Certificato trovato: $CERT_PATH"
else
    echo "   ✗ Certificato non generato automaticamente."
    echo "     Esegui: mitmdump --listen-port 18999"
    echo "     Aspetta 3 secondi, poi Ctrl+C, poi rilancia setup_macos.sh"
    exit 1
fi

# ── 3. Installa certificato nel Keychain di sistema ─────────────────
echo ""
echo "→ Installazione certificato nel Keychain (richiede password admin)..."
sudo security add-trusted-cert \
    -d \
    -r trustRoot \
    -k /Library/Keychains/System.keychain \
    "$CERT_PATH" && echo "   ✓ Certificato installato e fidato" \
               || echo "   ⚠ Certificato già presente o errore — continua comunque"

# ── 4. Verifica path TradingView ────────────────────────────────────
echo ""
echo "→ Verifica path TradingView..."
if [ -f "/Applications/TradingView.app/Contents/MacOS/TradingView" ]; then
    echo "   ✓ TradingView trovato"
else
    echo "   ⚠ TradingView non trovato in /Applications — controlla il path in start.sh"
fi

# ── 5. Salva il percorso del progetto ───────────────────────────────
echo ""
echo "→ Salvataggio percorso progetto..."
PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.mytradingguard"
echo "$PROJ_DIR" > "$HOME/.mytradingguard/project_path"
echo "   ✓ Percorso salvato: $PROJ_DIR"

# ── Riepilogo ────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Setup completato!                                       ║"
echo "║                                                          ║"
echo "║  Come usare MyTradingGuard ogni giorno:                  ║"
echo "║  1. Personalizza config.json con le tue regole           ║"
echo "║  2. Apri MyTradingGuard.app — avvia tutto automaticamente║"
echo "║                                                          ║"
echo "║  ✓ Il proxy di sistema NON viene modificato.             ║"
echo "║    Solo TradingView passa dal proxy MyTradingGuard.      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
