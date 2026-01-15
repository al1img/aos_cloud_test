"""Base command class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Command(ABC):
    """Base class for commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name."""
        ...

    @property
    @abstractmethod
    def help_args(self) -> str:
        """Arguments format for the command."""
        ...

    @property
    @abstractmethod
    def help(self) -> str:
        """Help text for the command."""
        ...

    @abstractmethod
    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Execute the command.

        Args:
            args: Command arguments
            context: Context with server references
        """
        ...
