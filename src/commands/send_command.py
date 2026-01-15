"""Send command implementation."""

import json
import logging
import os
from typing import Any, Dict, List

from .base import Command


class SendCommand(Command):
    """Send file content via WebSocket."""

    @property
    def name(self) -> str:
        return "send"

    @property
    def help_args(self) -> str:
        return "<file_path>"

    @property
    def help(self) -> str:
        return "Read file and send content via WebSocket to unit"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Read file and send content via WebSocket.

        Args:
            args: Command arguments containing file path
            context: Context with server references
        """
        if len(args) < 1:
            raise ValueError("send command requires a file path")

        file_path = args[0]

        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a file: {file_path}")

        websocket_server = context.get("websocket_server")

        if not websocket_server:
            raise RuntimeError("WebSocket server not available")

        try:
            # Read file content
            with open(file_path, "rb") as f:
                data = f.read()

            logging.info("Read %d bytes from file: %s", len(data), file_path)

            # Send via WebSocket
            await websocket_server.send_message(json.loads(data.decode("utf-8")))

            print(f"Successfully sent {len(data)} bytes from {file_path}")

        except RuntimeError as e:
            logging.error("Fail to send message: %s", e)

            raise

        except Exception as e:
            logging.error("Error reading or sending file: %s", e)

            raise
