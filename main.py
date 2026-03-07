"""
MyTradingGuard — main entry point.

Starts the mitmproxy proxy in the background and shows a live
dashboard in the terminal with real-time rule status.

Usage:
    python main.py
"""

from __future__ import annotations

import asyncio
import signal
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import Config
from rules_engine import RulesEngine
from trade_state import TradeState
from ui_state_writer import UIStateWriter

console = Console()


# ------------------------------------------------------------------ #
#  Dashboard                                                          #
# ------------------------------------------------------------------ #

def build_dashboard(state: TradeState, cfg: Config, engine: RulesEngine) -> Table:
    tz = pytz.timezone(cfg.time_window.timezone)
    now_local = datetime.now(tz)
    now = datetime.now()

    root = Table.grid(expand=True)
    root.add_column()

    # ── Titolo ────────────────────────────────────────────────────── #
    root.add_row(
        Panel(
            Text("⚡ MyTradingGuard", style="bold white", justify="center"),
            subtitle=f"[dim]{now_local.strftime('%A %d %b %Y  %H:%M:%S')} {cfg.time_window.timezone}[/dim]",
            style="bold blue",
        )
    )

    # ── Stato regole ─────────────────────────────────────────────── #
    rules_table = Table(box=box.ROUNDED, expand=True, show_header=False)
    rules_table.add_column("Icon", width=3)
    rules_table.add_column("Rule", style="bold")
    rules_table.add_column("Detail", style="dim")

    # Rule 1: Time window
    ok_time, msg_time = engine.check_time_window(state, cfg)
    tw = cfg.time_window
    if not tw.active:
        detail_time = "[dim]Disabled[/dim]"
    elif tw.windows:
        windows_str = " | ".join(f"{w['start']}–{w['end']}" for w in tw.windows)
        detail_time = f"{windows_str} ({tw.timezone})"
    else:
        detail_time = "No restriction"
    rules_table.add_row(
        "⚪" if not tw.active else ("🟢" if ok_time else "🔴"),
        "Time Window",
        detail_time if not tw.active else (
            f"[green]{detail_time}[/green]" if ok_time else f"[red]{msg_time}[/red]"
        ),
    )

    # Rule 2: Cooldown
    ok_cd, msg_cd = engine.check_cooldown(state, cfg)
    cd = cfg.cooldown
    last = state.last_trade_time
    if not cd.active:
        detail_cd = "[dim]Disabled[/dim]"
    elif cd.minutes > 0:
        if last:
            elapsed = now - last
            remaining = timedelta(minutes=cd.minutes) - elapsed
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                detail_cd = f"Unlocks in {mins}m {secs}s"
            else:
                detail_cd = f"Last trade: {last.strftime('%H:%M:%S')} ✓"
        else:
            detail_cd = "No trades today"
    else:
        detail_cd = "No restriction"
    rules_table.add_row(
        "⚪" if not cd.active else ("🟢" if ok_cd else "🔴"),
        f"Cooldown ({cd.minutes}min)",
        detail_cd if not cd.active else (
            f"[green]{detail_cd}[/green]" if ok_cd else f"[red]{detail_cd}[/red]"
        ),
    )

    # Rule 3: Max trades
    ok_max, _ = engine.check_max_trades(state, cfg)
    mt = cfg.max_daily_trades
    count = state.daily_count
    if not mt.active:
        detail_max = "[dim]Disabled[/dim]"
    else:
        bar = _progress_bar(count, mt.value)
        detail_max = f"{bar}  {count}/{mt.value}"
    rules_table.add_row(
        "⚪" if not mt.active else ("🟢" if ok_max else "🔴"),
        "Max Daily Trades",
        detail_max if not mt.active else (
            f"[green]{detail_max}[/green]" if ok_max else f"[red]{detail_max}[/red]"
        ),
    )

    # Rule 4: Max daily losses
    ok_loss, _ = engine.check_max_losses(state, cfg)
    ml = cfg.max_daily_losses
    losses = state.daily_losses
    if not ml.active:
        detail_loss = "[dim]Disabled[/dim]"
    else:
        bar_loss = _progress_bar(losses, ml.value)
        detail_loss = f"{bar_loss}  {losses}/{ml.value}"
    rules_table.add_row(
        "⚪" if not ml.active else ("🟢" if ok_loss else "🔴"),
        "Max Daily Losses",
        detail_loss if not ml.active else (
            f"[green]{detail_loss}[/green]" if ok_loss else f"[red]{detail_loss}[/red]"
        ),
    )

    # Rule 5: Max order size (static display)
    ms = cfg.max_order_size
    rules_table.add_row(
        "⚪" if not ms.active else "🟢",
        "Max Order Size",
        "[dim]Disabled[/dim]" if not ms.active else
        f"[green]Max {ms.value} contract(s) per order[/green]",
    )

    # Global status
    all_ok = ok_time and ok_cd and ok_max and ok_loss
    global_status = (
        Panel("[bold green]✅  TRADING ENABLED[/bold green]", style="green")
        if all_ok
        else Panel("[bold red]🚫  TRADING BLOCKED[/bold red]", style="red")
    )

    root.add_row(
        Columns([Panel(rules_table, title="[bold]Active Rules[/bold]"), global_status])
    )

    # ── Recent events log ─────────────────────────────────────────── #
    events = state.events[-8:]
    if events:
        log_table = Table(box=box.SIMPLE, expand=True, show_header=True)
        log_table.add_column("Time", style="dim", width=10)
        log_table.add_column("Type", width=10)
        log_table.add_column("Detail")

        for ev in reversed(events):
            ts_str = ev["ts"].strftime("%H:%M:%S")
            kind = ev["kind"]
            detail = ev["detail"]
            if kind == "BLOCKED":
                style = "red"
                icon = "🔴 BLOCKED"
            elif kind == "PASSED":
                style = "green"
                icon = "🟢 PASSED"
            elif kind == "LOSS":
                style = "red"
                icon = "📉 LOSS"
            elif kind == "WIN":
                style = "green"
                icon = "📈 WIN"
            else:
                style = "dim"
                icon = f"• {kind}"
            log_table.add_row(ts_str, f"[{style}]{icon}[/{style}]", detail)

        root.add_row(Panel(log_table, title="[bold]Recent Events[/bold]"))

    # ── Footer ───────────────────────────────────────────────────── #
    root.add_row(
        Text(
            f"  Proxy running on localhost:{cfg.proxy_port}  •  "
            f"Broker: {cfg.broker.title()} ({cfg.broker_env.upper()})  •  "
            "Ctrl+C to quit",
            style="dim",
            justify="center",
        )
    )

    return root


def _progress_bar(value: int, max_val: int, width: int = 10) -> str:
    filled = min(int(value / max_val * width), width) if max_val else 0
    bar = "█" * filled + "░" * (width - filled)
    return f"[{'green' if value < max_val else 'red'}]{bar}[/]"


# ------------------------------------------------------------------ #
#  Proxy runner                                                       #
# ------------------------------------------------------------------ #

def run_proxy(cfg: Config, state: TradeState):
    """Starts mitmproxy programmatically in a separate thread."""
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from proxy_addon import MyTradingGuardAddon

    async def _run():
        # allow_hosts: mitmproxy decrypts SSL ONLY for these hosts.
        # Everything else (TradingView login, market data, WebSocket, etc.)
        # passes as an opaque tunnel — no interference.
        opts = Options(
            listen_host="127.0.0.1",
            listen_port=cfg.proxy_port,
            ssl_insecure=True,
            allow_hosts=[
                "live.tradovateapi.com",
                "demo.tradovateapi.com",
                "tv-live.tradovateapi.com",
                "tv-demo.tradovateapi.com",
            ],
        )
        master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        master.addons.add(MyTradingGuardAddon(state=state, cfg=cfg))
        try:
            await master.run()
        except KeyboardInterrupt:
            master.shutdown()

    asyncio.run(_run())


# ------------------------------------------------------------------ #
#  Main                                                               #
# ------------------------------------------------------------------ #

def main():
    console.print()
    console.print("[bold blue]MyTradingGuard[/bold blue] — starting up...\n")

    # Load configuration
    try:
        cfg = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]ERROR:[/red] {e}")
        sys.exit(1)

    state = TradeState()
    engine = RulesEngine()

    # Start UI state writer (feeds the native macOS app)
    ui_writer = UIStateWriter(state=state, cfg=cfg, engine=engine)
    ui_writer.start()

    # Start proxy in a separate thread
    proxy_thread = threading.Thread(
        target=run_proxy, args=(cfg, state), daemon=True
    )
    proxy_thread.start()
    console.print(f"[green]✓[/green] Proxy started on [bold]localhost:{cfg.proxy_port}[/bold]")
    console.print(
        f"[green]✓[/green] Broker: [bold]{cfg.broker.title()}[/bold] "
        f"([yellow]{cfg.broker_env.upper()}[/yellow])\n"
    )

    # Live dashboard (updated every second)
    with Live(
        build_dashboard(state, cfg, engine),
        refresh_per_second=1,
        console=console,
        screen=True,
    ) as live:
        try:
            while True:
                import time
                time.sleep(1)
                live.update(build_dashboard(state, cfg, engine))
        except KeyboardInterrupt:
            pass

    console.print("\n[bold]MyTradingGuard stopped.[/bold] See you next time! 👋\n")


if __name__ == "__main__":
    main()
