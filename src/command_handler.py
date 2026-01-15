"""Command handler for console input."""

import asyncio
import logging
import os
import readline
import traceback
from typing import Any, Dict, Optional

from .commands import Command, HelpCommand, LogLevelCommand, QuitCommand, SendCommand, UpdateCommand


class CommandHandler:
    """Handler for console commands."""

    def __init__(self, websocket_server=None, http_server=None, file_server=None, config=None):
        """
        Initialize command handler.

        Args:
            websocket_server: WebSocket server instance for commands
            http_server: HTTP server instance for commands
            file_server: File server instance for commands
            config: Configuration dictionary
        """
        self.websocket_server = websocket_server
        self.http_server = http_server
        self.file_server = file_server
        self.config = config or {}
        self.commands: Dict[str, Command] = {}
        self.running = True
        self.history_file = os.path.expanduser(".aos_cloud_test_history")
        self._setup_history()
        self._register_commands()

    def _completer(self, text: str, state: int) -> Optional[str]:
        """Custom completer for command names.

        Args:
            text: Current text being completed
            state: Current completion state

        Returns:
            Next matching command or None
        """
        # Get line buffer and check if we're completing the first word
        line = readline.get_line_buffer()
        words = line.lstrip().split()

        # Only complete command names (first word)
        if not words or (len(words) == 1 and not line.endswith(" ")):
            options = [cmd for cmd in self.commands.keys() if cmd.startswith(text)]
            if state < len(options):
                return options[state]

        return None

    def _setup_history(self):
        """Setup readline history and completion."""
        try:
            # Configure readline
            readline.parse_and_bind("tab: complete")
            
            # Enable history search with up/down arrows
            # This allows filtering history by prefix when typing
            readline.parse_and_bind("\"\\e[A\": history-search-backward")
            readline.parse_and_bind("\"\\e[B\": history-search-forward")
            
            readline.set_completer(self._completer)
            readline.set_completer_delims(" \t\n")
            readline.set_history_length(1000)

            # Load history file if it exists
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)

                logging.info("Load command history from %s", self.history_file)

        except Exception as e:
            logging.warning("Fail to setup history: %s", e)

    def _save_history(self):
        """Save command history to file."""
        try:
            readline.write_history_file(self.history_file)

            logging.info("Save command history to %s", self.history_file)

        except Exception as e:
            logging.warning("Fail to save history: %s", e)

    def _register_commands(self):
        """Register available commands."""
        command_instances = [
            HelpCommand(),
            SendCommand(),
            LogLevelCommand(),
            UpdateCommand(),
            QuitCommand(),
        ]

        for cmd in command_instances:
            self.commands[cmd.name] = cmd

    def _get_context(self) -> Dict[str, Any]:
        """Get context dictionary for command execution."""
        return {
            "websocket_server": self.websocket_server,
            "http_server": self.http_server,
            "file_server": self.file_server,
            "config": self.config,
            "commands": self.commands,
            "handler": self,
        }

    async def process_command(self, command_line: str):
        """
        Process a command line input.

        Args:
            command_line: Full command line string
        """
        parts = command_line.strip().split()
        if not parts:
            return

        command = parts[0].lower()
        args = parts[1:]

        if command in self.commands:
            try:
                context = self._get_context()
                await self.commands[command].execute(args, context)
            except Exception as e:
                print(f"Error: {e}")

                # Display usage for the command
                cmd = self.commands[command]
                if cmd.help_args:
                    print(f"Usage: {cmd.name} {cmd.help_args}")

                print(traceback.format_exc())
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")

    async def run(self):
        """Run the command handler loop."""
        logging.info("Start command handler. Type 'help' for available commands")

        print("\nCommand handler ready. Type 'help' for available commands.")

        loop = asyncio.get_event_loop()

        while self.running:
            try:
                # Read from stdin asynchronously using input() which supports readline
                command_line = await loop.run_in_executor(None, input, "# ")

                if not command_line:
                    continue

                await self.process_command(command_line)

            except EOFError:
                # EOF reached (Ctrl+D)
                break
            except KeyboardInterrupt:
                logging.info("Receive keyboard interrupt")

                print("\n\nUse 'quit' command to shutdown gracefully.")
            except Exception as e:
                logging.error("Error in command handler: %s", e)

        # Save history on exit
        self._save_history()

        logging.info("Stop command handler")
