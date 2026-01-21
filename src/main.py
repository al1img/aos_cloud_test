#!/usr/bin/env python3
"""
Multi-Server Application
Implements HTTP, WebSocket, and File servers with JSON configuration support.
"""

import asyncio
import logging
import signal
import sys
import threading
from pathlib import Path

from .command_handler import CommandHandler
from .config_loader import ConfigLoader
from .file_server import FileServer
from .http_server import HTTPServer
from .messages import Messages
from .websocket_server import WebSocketServer


class AosCloud:
    """Main application managing all servers."""

    def __init__(self, config_path: str = "config.json"):
        # Setup basic logging first
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Resolve config path relative to project root
        if not Path(config_path).is_absolute():
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / config_path)

        self.config = ConfigLoader.load(config_path)
        self.threads = []
        self.http_server = None
        self.ws_server = None
        self.file_server = None
        self.messages = None
        self.command_handler = None
        self._setup_logging()  # Reconfigure with config settings

    def start(self):
        """Start all servers."""
        logging.info("Start Aos test cloud")

        # Start File Server first so it's available for WebSocket
        self.file_server = FileServer(self.config)
        file_thread = threading.Thread(target=self.file_server.start, daemon=True)
        file_thread.start()
        self.threads.append(file_thread)

        # Start HTTP Server in thread
        self.http_server = HTTPServer(self.config)
        http_thread = threading.Thread(target=self.http_server.start, daemon=True)
        http_thread.start()
        self.threads.append(http_thread)

        # Create Messages instance for WebSocket message tracking
        self.messages = Messages()

        # Start WebSocket Server in thread with file_server reference
        self.ws_server = WebSocketServer(self.config, file_server=self.file_server, messages=self.messages)
        ws_thread = threading.Thread(target=self.ws_server.start, daemon=True)
        ws_thread.start()
        self.threads.append(ws_thread)

        logging.info("Start all servers successfully")

        logging.info("Press Ctrl+C to stop the servers")

    def run(self):
        """Run the application until interrupted."""
        self.start()

        # Initialize command handler with server references
        self.command_handler = CommandHandler(
            websocket_server=self.ws_server,
            http_server=self.http_server,
            file_server=self.file_server,
            config=self.config,
        )

        # Run command handler in asyncio loop
        try:
            asyncio.run(self.command_handler.run())
        except KeyboardInterrupt:
            logging.info("Interrupt application")
        finally:
            sys.exit(0)

    def _setup_logging(self):
        """Configure logging based on config."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO"))
        uvicorn_level = getattr(logging, log_config.get("uvicornLevel", "INFO"))
        format_str = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Reconfigure root logger
        logging.basicConfig(level=level, format=format_str, force=True)

        # Set uvicorn loggers to different level
        logging.getLogger("uvicorn").setLevel(uvicorn_level)
        logging.getLogger("uvicorn.access").setLevel(uvicorn_level)
        logging.getLogger("uvicorn.error").setLevel(uvicorn_level)


def main():
    """Entry point for the application."""
    app = AosCloud()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logging.info("Receive interrupt signal")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        app.run()
    except Exception as e:
        logging.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
