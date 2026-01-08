"""HTTP server implementation."""

import json
import logging
from typing import Any, Dict

from aiohttp import web


class HTTPServer:
    """Simple HTTP server with basic routes."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = web.Application()
        self._setup_routes()

    async def handle_services_discovery(self, request: web.Request) -> web.Response:
        """Handle services discovery POST endpoint."""
        try:
            data = await request.json()

            logging.info("Received services discovery request: %s", data)

            # Process the discovery request and return response
            response = {
                "service": "HTTP Server",
                "status": "success",
                "received_data": data,
            }

            return web.json_response(response)
        except json.JSONDecodeError:
            logging.error("Invalid JSON in services discovery request")

            return web.json_response({"error": "Invalid JSON"}, status=400)

    async def start(self):
        """Start the HTTP server."""
        host = self.config["httpServer"]["host"]
        port = self.config["httpServer"]["port"]

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        logging.info("HTTP Server started on http://%s:%s", host, port)

        return runner

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post("/sd/v7/", self.handle_services_discovery)
