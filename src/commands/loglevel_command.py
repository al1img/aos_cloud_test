"""Log level command implementation."""

import logging
from typing import Any, Dict, List

from .base import Command


class LogLevelCommand(Command):
    """Change log level at runtime."""

    VALID_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @property
    def name(self) -> str:
        return "loglevel"

    @property
    def help_args(self) -> str:
        return "<level>"

    @property
    def help(self) -> str:
        return f"Change log level ({', '.join(self.VALID_LEVELS)})"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Change the log level at runtime.

        Args:
            args: Command arguments containing log level
            context: Context with server references
        """
        if len(args) < 1:
            raise ValueError(f"loglevel command requires a log level. Valid levels: {', '.join(self.VALID_LEVELS)}")

        level_str = args[0].upper()

        if level_str not in self.VALID_LEVELS:
            raise ValueError(f"Invalid log level '{level_str}'. Valid levels: {', '.join(self.VALID_LEVELS)}")

        try:
            level = getattr(logging, level_str)

            # Change root logger level
            logging.getLogger().setLevel(level)

            logging.info("Change log level to %s", level_str)

            print(f"Log level changed to {level_str}")

        except Exception as e:
            logging.error("Fail to change log level: %s", e)

            raise
