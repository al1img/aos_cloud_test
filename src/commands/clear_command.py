"""Clear command implementation."""

import logging
import os
import shutil
from typing import Any, Dict, List

from .base import Command


class ClearCommand(Command):
    """Clear files folder."""

    @property
    def name(self) -> str:
        return "clear"

    @property
    def help_args(self) -> str:
        return ""

    @property
    def help(self) -> str:
        return "Clear file server root directory"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Clear file server root directory.

        Args:
            args: Command arguments (none expected)
            context: Context with server references
        """
        config = context.get("config", {})
        root_directory = config.get("fileServer", {}).get("rootDirectory", "./files")

        logging.info("Clear file server root directory: %s", root_directory)

        if os.path.exists(root_directory):
            shutil.rmtree(root_directory)

            logging.info("File server root directory cleared")

        # Create sha256 directory for blobs
        sha256_dir = os.path.join(root_directory, "sha256")
        os.makedirs(sha256_dir, exist_ok=True)

        logging.info("Recreated sha256 directory: %s", sha256_dir)

        print(f"Cleared file server directory: {root_directory}")
