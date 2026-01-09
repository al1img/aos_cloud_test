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

from command_handler import CommandHandler
from config_loader import ConfigLoader
from file_server import FileServer
from http_server import HTTPServer
from websocket_server import WebSocketServer


class AosCloud:
    """Main application managing all servers."""

    def __init__(self, config_path: str = "config.json"):
        # Setup basic logging first
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        self.config = ConfigLoader.load(config_path)
        self.threads = []
        self.http_server = None
        self.ws_server = None
        self.file_server = None
        self.command_handler = None
        self._setup_logging()  # Reconfigure with config settings

    def start(self):
        """Start all servers."""
        logging.info("Start Aos test cloud...")

        # Start HTTP Server in thread
        self.http_server = HTTPServer(self.config)
        http_thread = threading.Thread(target=self.http_server.start, daemon=True)
        http_thread.start()
        self.threads.append(http_thread)

        # Start WebSocket Server in thread
        self.ws_server = WebSocketServer(self.config)
        ws_thread = threading.Thread(target=self.ws_server.start, daemon=True)
        ws_thread.start()
        self.threads.append(ws_thread)

        # Start File Server in thread
        self.file_server = FileServer(self.config)
        file_thread = threading.Thread(target=self.file_server.start, daemon=True)
        file_thread.start()
        self.threads.append(file_thread)

        logging.info("All servers started successfully!")

        logging.info("Press Ctrl+C to stop the servers")

    def run(self):
        """Run the application until interrupted."""
        self.start()

        # Initialize command handler with server references
        self.command_handler = CommandHandler(
            websocket_server=self.ws_server, http_server=self.http_server, file_server=self.file_server
        )

        # Run command handler in asyncio loop
        try:
            asyncio.run(self.command_handler.run())
        except KeyboardInterrupt:
            logging.info("Application interrupted")
        finally:
            sys.exit(0)

    def _setup_logging(self):
        """Configure logging based on config."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO"))
        format_str = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Reconfigure logging with force
        logging.basicConfig(level=level, format=format_str, force=True)


def main():
    """Entry point for the application."""
    app = AosCloud()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logging.info("Received interrupt signal")
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
