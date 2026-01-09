"""HTTP server implementation."""

import logging
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class HTTPServer:
    """Simple HTTP server with basic routes."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = FastAPI()
        self._setup_routes()

    async def handle_services_discovery(self, request: Request) -> JSONResponse:
        """Handle services discovery POST endpoint."""
        try:
            data = await request.json()

            logging.info("Receive services discovery request: %s", data)

            # Process the discovery request and return response
            response = {
                "version": 7,
                "connectionInfo": [
                    "ws://"
                    + self.config["websocketServer"]["host"]
                    + ":"
                    + str(self.config["websocketServer"]["port"])
                    + "/ws",
                ],
                "errorCode": 0,
            }

            return JSONResponse(content=response)
        except Exception as e:
            logging.error("Invalid JSON in services discovery request")

            raise HTTPException(status_code=400, detail="Invalid JSON")

    def start(self):
        """Start the HTTP server."""
        host = self.config["httpServer"]["host"]
        port = self.config["httpServer"]["port"]

        logging.info("Start HTTP Server on http://%s:%s", host, port)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_config=None,  # Disable uvicorn's logging to use our own
        )

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.post("/sd/v7/")(self.handle_services_discovery)
