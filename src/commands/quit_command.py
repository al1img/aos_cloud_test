"""Quit command implementation."""

import logging
from typing import Any, Dict, List

from .base import Command


class QuitCommand(Command):
    """Exit the application."""

    @property
    def name(self) -> str:
        return "quit"

    @property
    def help_args(self) -> str:
        return ""

    @property
    def help(self) -> str:
        return "Shutdown the application"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """Shutdown the application."""
        logging.info("Receive exit command, shut down")

        print("Shutting down...")

        handler = context.get("handler")

        if handler:
            handler.running = False
