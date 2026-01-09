"""WebSocket server implementation."""

import json
import logging
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse


class WebSocketServer:
    """WebSocket server for real-time communication."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = FastAPI()
        self.clients = set()
        self._setup_routes()

    async def handle_root(self) -> JSONResponse:
        """Handle root endpoint."""
        return JSONResponse(
            content={
                "service": "WebSocket Server",
                "status": "running",
                "endpoint": "/ws",
                "active_connections": len(self.clients),
            }
        )

    async def websocket_handler(self, websocket: WebSocket):
        """Handle WebSocket connections."""
        await websocket.accept()

        self.clients.add(websocket)

        logging.info("New WebSocket connection. Total clients: %d", len(self.clients))

        try:
            # Send welcome message
            # await websocket.send_json({"type": "welcome", "message": "Connected to WebSocket server"})

            while True:
                data = await websocket.receive_bytes()
                text = data.decode("utf-8")

                logging.info("Received WebSocket message: %s", text)

                message = json.loads(text)

                system_id = message["header"]["systemId"]
                txn = message["header"]["txn"]

                await websocket.send_json(self._create_ack_message(system_id, txn), "binary")

                """
                # Echo back to sender
                await websocket.send_json({"type": "echo", "data": data})

                # Broadcast to all other clients
                for client in self.clients:
                    if client != websocket:
                        try:
                            await client.send_json({"type": "broadcast", "data": data})
                        except Exception as e:
                            logging.error("Error broadcasting to client: %s", e)
                """

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logging.error("WebSocket error: %s", e)
        finally:
            self.clients.discard(websocket)

            logging.info("WebSocket disconnected. Total clients: %d", len(self.clients))

    def start(self):
        """Start the WebSocket server."""
        host = self.config["websocketServer"]["host"]
        port = self.config["websocketServer"]["port"]

        logging.info("WebSocket Server started on ws://%s:%s/ws", host, port)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_config=None,  # Disable uvicorn's logging to use our own
        )

    def _create_ack_message(self, system_id: str, txn: str) -> Dict[str, Any]:
        """Create an acknowledgment message."""
        return {
            "header": {
                "version": 7,
                "systemId": system_id,
                "txn": txn,
            },
            "data": {
                "messageType": "ack",
            },
        }

    def _setup_routes(self):
        """Setup WebSocket routes."""
        self.app.websocket("/ws")(self.websocket_handler)
        self.app.get("/")(self.handle_root)
