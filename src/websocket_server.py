"""WebSocket server implementation."""

import json
import logging
import uuid
from typing import Any, Dict, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .messages import Messages


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

    def __init__(self, config: Dict[str, Any], file_server=None, messages: Optional[Messages] = None):
        self.config = config
        self.app = FastAPI()
        self.clients: Set[Client] = set()
        self.file_server = file_server
        self.messages = messages if messages else Messages()
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
                    logging.info("Set client system_id to: %s", system_id)

                    client.system_id = system_id

                logging.info("RX txn [%s] message [%s]", message["header"]["txn"], message["data"]["messageType"])

                if self.config["websocketServer"].get("prettifyReceivedMessages", False):
                    logging.debug("%s", json.dumps(message, indent=4, ensure_ascii=False))
                else:
                    logging.debug("%s", text)

                if message["data"]["messageType"] == "ack":
                    continue

                # Store received message
                self.messages.notify_received(system_id, txn, message["data"])

                await self.send_message({"messageType": "ack"}, client=client, txn=txn)
                await self._process_message(message["data"])

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

    async def send_message(self, data: Dict[str, Any], client: Optional[Client] = None, txn: Optional[str] = None):
        """
        Send message to last connected client.

        Args:
            data: Message data to send

        Raises:
            RuntimeError: If no clients are connected
        """

        if not client:
            if not self.clients:
                raise RuntimeError("No clients connected")

            # Get last connected client (most recent addition to the set)
            client = list(self.clients)[-1]

        message = {
            "header": self._create_header(client.system_id or "unknown", txn or str(uuid.uuid4())),
            "data": data,
        }

        text = json.dumps(message, separators=(",", ":"), ensure_ascii=False)

        logging.info("TX txn [%s] message [%s]", message["header"]["txn"], data["messageType"])

        if self.config["websocketServer"].get("prettifyReceivedMessages", False):
            logging.debug("%s", json.dumps(message, indent=4, ensure_ascii=False))
        else:
            logging.debug("%s", message)

        if data["messageType"] != "ack":
            self.messages.notify_sent(message["header"]["systemId"], message["header"]["txn"], data)

        await client.websocket.send_bytes(text.encode("utf-8"))

    def start(self):
        """Start the WebSocket server."""
        host = self.config["websocketServer"]["host"]
        port = self.config["websocketServer"]["port"]

        logging.info("Start WebSocket Server on ws://%s:%s/ws", host, port)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_config=None,  # Disable uvicorn's logging to use our own
        )

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

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process incoming WebSocket message."""
        try:
            if message["messageType"] == "requestBlobUrls":
                logging.info("Process requestBlobUrls message: %s", message["digests"])

                if not self.file_server:
                    logging.error("File server not available")

                    return

                # Get blob info for each digest
                blob_infos = []
                for digest in message["digests"]:
                    blob_info = self.file_server.get_blob_info(digest)
                    if blob_info:
                        blob_infos.append(blob_info)
                    else:
                        logging.warning("Blob info not found for digest: %s", digest)

                logging.debug("Blob infos: %s", blob_infos)

                await self.send_message(
                    {
                        "correlationId": message["correlationId"],
                        "messageType": "blobUrls",
                        "items": blob_infos,
                    }
                )

                logging.info("Find %d blob info", len(blob_infos))
        except Exception as e:
            logging.error("Error processing message: %s", e)
