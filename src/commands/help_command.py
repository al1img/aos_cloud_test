"""Help command implementation."""

from typing import Any, Dict, List

from .base import Command


class HelpCommand(Command):
    """Display available commands."""

    @property
    def name(self) -> str:
        return "help"

    @property
    def help_args(self) -> str:
        return ""

    @property
    def help(self) -> str:
        return "Display this help message"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """Display all available commands."""
        commands = context.get("commands", {})

        print("\nAos Cloud Test - Available Commands:")

        print()

        # Calculate max length for alignment
        max_len = max(len(cmd.name + " " + cmd.help_args) for cmd in commands.values())

        for cmd in commands.values():
            cmd_with_args = f"{cmd.name} {cmd.help_args}".strip()
            padding = max_len - len(cmd_with_args)
            print(f"{cmd_with_args}{' ' * padding} - {cmd.help}")

        print()
