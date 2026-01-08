"""WebSocket server implementation."""

import logging
from typing import Any, Dict

from aiohttp import WSMsgType, web


class WebSocketServer:
    """WebSocket server for real-time communication."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = web.Application()
        self.clients = set()
        self._setup_routes()

    async def handle_root(self, request: web.Request) -> web.Response:
        """Handle root endpoint."""
        return web.json_response(
            {
                "service": "WebSocket Server",
                "status": "running",
                "endpoint": "/ws",
                "active_connections": len(self.clients),
            }
        )

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.clients.add(ws)

        logging.info("New WebSocket connection. Total clients: %d", len(self.clients))

        try:
            # Send welcome message
            await ws.send_json(
                {"type": "welcome", "message": "Connected to WebSocket server"}
            )

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = msg.json()

                    logging.info("Received WebSocket message: %s", data)

                    # Echo back to sender
                    await ws.send_json({"type": "echo", "data": data})

                    # Broadcast to all other clients
                    for client in self.clients:
                        if client != ws:
                            try:
                                await client.send_json(
                                    {"type": "broadcast", "data": data}
                                )
                            except Exception as e:
                                logging.error("Error broadcasting to client: %s", e)

                elif msg.type == WSMsgType.ERROR:
                    logging.error("WebSocket error: %s", ws.exception())

        finally:
            self.clients.discard(ws)

            logging.info("WebSocket disconnected. Total clients: %d", len(self.clients))

        return ws

    async def start(self):
        """Start the WebSocket server."""
        host = self.config["websocketServer"]["host"]
        port = self.config["websocketServer"]["port"]

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        logging.info("WebSocket Server started on ws://%s:%s/ws", host, port)

        return runner

    def _setup_routes(self):
        """Setup WebSocket routes."""
        self.app.router.add_get("/ws", self.websocket_handler)
        self.app.router.add_get("/", self.handle_root)
