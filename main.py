#!/usr/bin/env python3
"""
Multi-Server Application
Implements HTTP, WebSocket, and File servers with JSON configuration support.
"""

import asyncio
import logging
import signal

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
        self.runners = []
        self._setup_logging()  # Reconfigure with config settings

    async def start(self):
        """Start all servers."""
        logging.info("Start Aos test cloud...")

        # Start HTTP Server
        http_server = HTTPServer(self.config)
        http_runner = await http_server.start()
        self.runners.append(http_runner)

        # Start WebSocket Server
        ws_server = WebSocketServer(self.config)
        ws_runner = await ws_server.start()
        self.runners.append(ws_runner)

        # Start File Server
        file_server = FileServer(self.config)
        file_runner = await file_server.start()
        self.runners.append(file_runner)

        logging.info("All servers started successfully!")

        logging.info("Press Ctrl+C to stop the servers")

    async def stop(self):
        """Stop all servers gracefully."""
        logging.info("Stopping servers...")

        for runner in self.runners:
            await runner.cleanup()

        logging.info("All servers stopped")

    async def run(self):
        """Run the application until interrupted."""
        await self.start()

        # Wait for interrupt signal
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    def _setup_logging(self):
        """Configure logging based on config."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO"))
        format_str = log_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Reconfigure logging with force
        logging.basicConfig(level=level, format=format_str, force=True)


async def main():
    """Entry point for the application."""
    app = AosCloud()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logging.info("Received interrupt signal")

        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await app.run()
    except KeyboardInterrupt:
        logging.info("Application interrupted")
    except Exception as e:
        logging.error("Application error: %s", e, exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
