# ⚡ MyTradingGuard

Software di autodisciplina per il trading su TradingView Desktop (macOS).
Blocca l'invio di ordini al broker se le regole impostate non sono soddisfatte.

## Come funziona

```
TradingView App ──► [Proxy locale :8080] ──► Tradovate API
                            │
                      Controlla regole:
                      • Fascia oraria ✓/✗
                      • Cooldown ✓/✗  
                      • Max trade/giorno ✓/✗
```

Il proxy intercetta le chiamate HTTP che TradingView invia a Tradovate.
Se le regole non sono soddisfatte, la richiesta viene bloccata **prima**
di raggiungere il broker — l'ordine non parte.

---

## Installazione (una tantum)

### 1. Installa le dipendenze

```bash
pip3 install -r requirements.txt
```

### 2. Esegui il setup macOS

```bash
bash setup_macos.sh
```

Questo script:
- Genera il certificato SSL di mitmproxy
- Lo installa nel Keychain di sistema come **trusted** (richiede password admin)
- Configura il proxy di sistema su Wi-Fi (porta 8080)

> ⚠️ Il certificato è necessario per intercettare il traffico HTTPS.
> È generato localmente sul tuo Mac e non viene mai trasmesso.

---

## Configurazione regole

Modifica `config.json`:

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

| Campo | Descrizione |
|-------|-------------|
| `time_windows` | Fasce orarie in cui il trading è **permesso**. Fuori da questi orari gli ordini vengono bloccati. |
| `timezone` | Timezone per le fasce orarie (`America/New_York`, `Europe/Rome`, ecc.) |
| `cooldown_minutes` | Minuti di attesa obbligatoria dopo ogni operazione. `0` = disabilitato |
| `max_daily_trades` | Numero massimo di ordini al giorno. `0` = disabilitato |
| `broker` | `tradovate` oppure `interactive_brokers` |
| `broker_env` | `live` oppure `demo` |

**La configurazione viene riletta automaticamente** ogni volta che salvi il file — non devi riavviare MyTradingGuard.

---

## Uso quotidiano

```bash
python main.py
```

Si apre il dashboard nel terminale:

```
╔═══════════════════════════════╗
║       ⚡ MyTradingGuard            ║
║  Friday 06 Mar 2026  10:42:33 ║
╚═══════════════════════════════╝

┌─ Regole Attive ──────────────────────────────┐
│ 🟢  Fascia Oraria        09:30–11:30 ✓       │
│ 🔴  Cooldown (5min)      Sblocco tra 3m 12s  │
│ 🟢  Max Op/Giorno        ████░░░░░░  2/3      │
└──────────────────────────────────────────────┘

         🚫  TRADING BLOCCATO

┌─ Ultimi eventi ──────────────────────────────┐
│ 10:41:15  🔴 BLOCCO  Cooldown attivo: ...    │
│ 10:38:02  🟢 PASS    LONG NQ                 │
└──────────────────────────────────────────────┘
```

---

## Rimuovere il proxy

Quando hai finito di usare MyTradingGuard (o hai problemi di connessione):

```bash
bash teardown_macos.sh
```

Questo disabilita il proxy di sistema — la connessione torna diretta.

---

## Struttura del progetto

```
mytradingguard/
├── main.py           # Entry point + dashboard terminale
├── proxy_addon.py    # Addon mitmproxy — intercetta gli ordini
├── rules_engine.py   # Motore delle regole
├── trade_state.py    # Stato giornaliero (persistente)
├── config.py         # Caricamento configurazione
├── config.json       # ← Personalizza qui le tue regole
├── setup_macos.sh    # Setup macOS (eseguire una volta)
├── teardown_macos.sh # Rimuovi proxy
└── requirements.txt
```

---

## Aggiungere un nuovo broker

Modifica `BROKER_PATTERNS` in `proxy_addon.py`:

```python
"my_broker": {
    "hosts": ["api.mybroker.com"],
    "order_paths": [r"/v1/orders", r"/api/place"],
    "success_field": "order_id",
},
```

---

## Risoluzione problemi

**TradingView non si connette dopo il setup**
→ Assicurati che `python main.py` sia in esecuzione prima di aprire TradingView.

**Errore certificato SSL**
→ Apri Keychain Access → Sistema → cerca "mitmproxy" → doppio click → Fidati sempre.

**Il proxy blocca siti non legati al broker**
→ Normale: mitmproxy fa da proxy per tutto il traffico, ma MyTradingGuard interviene
  solo sugli endpoint del broker. Il resto transita invariato.

**Cambiare da Wi-Fi a Ethernet**
→ Modifica `SERVICE="Ethernet"` in entrambi gli script `.sh` e riesegui il setup.
