"""
Debug proxy — logga OGNI richiesta verso Tradovate con URL completo.
"""
import asyncio
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster


class DebugAddon:
    def request(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host
        if "tradovate" not in host.lower():
            return

        method = flow.request.method
        path = flow.request.path
        query = flow.request.query

        # Stampa tutto — path + query string completa
        query_str = "&".join(f"{k}={v}" for k, v in query.items())
        full = f"{path}?{query_str}" if query_str else path
        print(f"[{method}] {host}{full}", flush=True)

        # Evidenzia se contiene parametri che sembrano un ordine
        order_keys = {"side", "instrument", "qty", "type", "action", "symbol"}
        found = order_keys & set(query.keys())
        if found or method == "POST":
            print(f"  >>> POSSIBILE ORDINE — chiavi trovate: {found or 'POST body'}", flush=True)
            if method == "POST":
                try:
                    print(f"  BODY: {flow.request.content[:300]}", flush=True)
                except Exception:
                    pass


async def run():
    opts = Options(
        listen_host="127.0.0.1",
        listen_port=8080,
        ssl_insecure=True,
        allow_hosts=[
            "live.tradovateapi.com",
            "demo.tradovateapi.com",
            "tv-live.tradovateapi.com",
            "tv-demo.tradovateapi.com",
        ],
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(DebugAddon())
    print("=== Debug proxy attivo su :8080 ===", flush=True)
    print("Piazza un ordine su TradingView e osserva qui sotto", flush=True)
    print("=" * 40, flush=True)
    await master.run()


asyncio.run(run())
