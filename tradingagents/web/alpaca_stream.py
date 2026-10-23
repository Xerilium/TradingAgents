"""Configured Alpaca trade_updates over the pinned websockets client."""

import asyncio
import json


class PaperStream:
    async def connect(self, connection):
        from websockets.asyncio.client import connect
        class FixedTradingOrigin(connect):
            def process_redirect(self, exc):
                return exc
        self.socket = await FixedTradingOrigin(connection.stream_url, open_timeout=20,
                                    max_size=1024 * 1024, max_queue=16, compression=None)
        secret = connection.headers()
        await self.send({"action": "auth", "key": secret["APCA-API-KEY-ID"], "secret": secret["APCA-API-SECRET-KEY"]})
        response = await asyncio.wait_for(self.receive(), 20)
        if response.get("stream") != "authorization" or response.get("data", {}).get("status") != "authorized":
            raise ValueError("Alpaca stream authentication failed")
        await self.send({"action": "listen", "data": {"streams": ["trade_updates"]}})
        response = await asyncio.wait_for(self.receive(), 20)
        if response.get("stream") != "listening" or response.get("data", {}).get("streams") != ["trade_updates"]:
            raise ValueError("Alpaca trade-update subscription was not acknowledged")

    async def send(self, value):
        await self.socket.send(json.dumps(value, allow_nan=False))

    async def receive(self):
        payload = await self.socket.recv()
        result = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload, parse_float=str)
        if not isinstance(result, dict):
            raise ValueError("Unexpected paper stream message schema")
        return result

    async def close(self):
        if getattr(self, "socket", None):
            await self.socket.close()
