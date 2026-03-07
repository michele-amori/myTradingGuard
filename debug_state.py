"""
Captures the JSON response of /accounts/{id}/state from Tradovate.
Run with TradingView open, prints the first state response and exits.
"""
import asyncio, json
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster


class StateCapture:
    def __init__(self):
        self.captured = False

    def response(self, flow: http.HTTPFlow):
        if self.captured:
            return
        host = flow.request.pretty_host
        path = flow.request.path
        if "tradovate" in host and "/state" in path:
            try:
                body = json.loads(flow.response.content)
                print("\n=== STATE RESPONSE ===")
                print(json.dumps(body, indent=2))
                print("======================\n")
                self.captured = True
            except Exception as e:
                print(f"Parse error: {e}")


async def run():
    opts = Options(
        listen_host="127.0.0.1", listen_port=8080,
        ssl_insecure=True,
        allow_hosts=["tv-demo.tradovateapi.com", "tv-live.tradovateapi.com",
                     "demo.tradovateapi.com", "live.tradovateapi.com"],
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(StateCapture())
    print("Waiting for a state response... (TradingView must be open)")
    await master.run()

asyncio.run(run())
