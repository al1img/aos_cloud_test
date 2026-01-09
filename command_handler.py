"""Command handler for console input."""

import asyncio
import json
import logging
import os
import readline
import rlcompleter
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Command(ABC):
    """Base class for commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name."""
        pass

    @property
    @abstractmethod
    def help_args(self) -> str:
        """Arguments format for the command."""
        pass

    @property
    @abstractmethod
    def help(self) -> str:
        """Help text for the command."""
        pass

    @abstractmethod
    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Execute the command.

        Args:
            args: Command arguments
            context: Context with server references
        """
        pass


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
            print("Error: send command requires a file path")
            print("Usage: send <file_path>")

            return

        file_path = args[0]

        # Validate file exists
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")

            return

        if not os.path.isfile(file_path):
            print(f"Error: Path is not a file: {file_path}")

            return

        websocket_server = context.get("websocket_server")

        if not websocket_server:
            print("Error: WebSocket server not available")

            return

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

            print(f"Error: {e}")

        except Exception as e:
            logging.error("Error reading or sending file: %s", e)

            print(f"Error: {e}")


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
            print("Error: loglevel command requires a log level")
            print(f"Usage: loglevel <level>")
            print(f"Valid levels: {', '.join(self.VALID_LEVELS)} (case insensitive)")

            return

        level_str = args[0].upper()

        if level_str not in self.VALID_LEVELS:
            print(f"Error: Invalid log level '{level_str}'")
            print(f"Valid levels: {', '.join(self.VALID_LEVELS)}")

            return

        try:
            level = getattr(logging, level_str)

            # Change root logger level
            logging.getLogger().setLevel(level)

            logging.info("Change log level to %s", level_str)

            print(f"Log level changed to {level_str}")

        except Exception as e:
            logging.error("Fail to change log level: %s", e)

            print(f"Error: {e}")


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


class CommandHandler:
    """Handler for console commands."""

    def __init__(self, websocket_server=None, http_server=None, file_server=None):
        """
        Initialize command handler.

        Args:
            websocket_server: WebSocket server instance for commands
            http_server: HTTP server instance for commands
            file_server: File server instance for commands
        """
        self.websocket_server = websocket_server
        self.http_server = http_server
        self.file_server = file_server
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
                logging.error("Error executing command '%s': %s", command, e)

                print(f"Error executing command: {e}")
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
