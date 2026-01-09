"""WebSocket server implementation."""

import json
import logging
import uuid
from typing import Any, Dict, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse


class Client:
    """WebSocket client wrapper."""

    def __init__(self, websocket: WebSocket):
        """
        Initialize client.

        Args:
            websocket: WebSocket connection
        """
        self.websocket = websocket
        self.system_id: Optional[str] = None


class WebSocketServer:
    """WebSocket server for real-time communication."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = FastAPI()
        self.clients: Set[Client] = set()
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

        client = Client(websocket)
        self.clients.add(client)

        logging.info("New WebSocket connection. Total clients: %d", len(self.clients))

        try:
            # Send welcome message
            # await websocket.send_json({"type": "welcome", "message": "Connected to WebSocket server"})

            while True:
                data = await websocket.receive_bytes()
                text = data.decode("utf-8")

                message = json.loads(text)

                system_id = message["header"]["systemId"]
                txn = message["header"]["txn"]

                # Set system_id on first message from this client
                if client.system_id is None:
                    client.system_id = system_id

                    logging.info("Client system_id set to: %s", system_id)

                logging.info("Received WebSocket message: [%s]", message["data"]["messageType"])
                logging.debug("%s", text)

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
            self.clients.discard(client)

            if client.system_id:
                logging.info("WebSocket disconnected [%s]. Total clients: %d", client.system_id, len(self.clients))
            else:
                logging.info("WebSocket disconnected. Total clients: %d", len(self.clients))

    async def send_message(self, data: bytes):
        """
        Send message to last connected client.

        Args:
            data: Message data to send

        Raises:
            RuntimeError: If no clients are connected
        """
        if not self.clients:
            raise RuntimeError("No clients connected")

        # Get last connected client (most recent addition to the set)
        client = list(self.clients)[-1]

        logging.info("Sending message to client [%s]", client.system_id or "unknown")

        text = data.decode("utf-8")

        message = {
            "header": self._create_header(client.system_id or "unknown", str(uuid.uuid4())),
            "data": json.loads(text),
        }

        await client.websocket.send_json(message, "binary")

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
            "header": self._create_header(system_id, txn),
            "data": {
                "messageType": "ack",
            },
        }

    def _create_header(self, system_id: str, txn: str) -> None:
        return {
            "version": 7,
            "systemId": system_id,
            "txn": txn,
        }

    def _setup_routes(self):
        """Setup WebSocket routes."""
        self.app.websocket("/ws")(self.websocket_handler)
        self.app.get("/")(self.handle_root)
