"""Command handler for console input."""

import asyncio
import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List


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


class TestCommand(Command):
    """Test command that echoes parameters."""

    @property
    def name(self) -> str:
        return "test"

    @property
    def help_args(self) -> str:
        return "<param1> <param2>"

    @property
    def help(self) -> str:
        return "Test command with two parameters"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """Echo parameters and show WebSocket client count."""
        if len(args) < 2:
            print("Error: test command requires 2 parameters")
            print("Usage: test <param1> <param2>")

            return

        param1, param2 = args[0], args[1]

        logging.info("Test command executed with params: %s, %s", param1, param2)

        print(f"Test command executed:")
        print(f"  Parameter 1: {param1}")
        print(f"  Parameter 2: {param2}")

        websocket_server = context.get("websocket_server")

        if websocket_server:
            print(f"  Active WebSocket clients: {len(websocket_server.clients)}")


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
            await websocket_server.send_message(data)

            print(f"Successfully sent {len(data)} bytes from {file_path}")

        except RuntimeError as e:
            logging.error("Failed to send message: %s", e)

            print(f"Error: {e}")

        except Exception as e:
            logging.error("Error reading or sending file: %s", e)

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
        logging.info("Exit command received, shutting down...")

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
        self._register_commands()

    def _register_commands(self):
        """Register available commands."""
        command_instances = [
            HelpCommand(),
            TestCommand(),
            SendCommand(),
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
        logging.info("Command handler started. Type 'help' for available commands.")

        print("\nCommand handler ready. Type 'help' for available commands.")

        loop = asyncio.get_event_loop()

        while self.running:
            try:
                # Display prompt
                sys.stdout.write("# ")
                sys.stdout.flush()

                # Read from stdin asynchronously
                command_line = await loop.run_in_executor(None, sys.stdin.readline)

                if not command_line:
                    # EOF reached
                    break

                await self.process_command(command_line)

            except KeyboardInterrupt:
                logging.info("Keyboard interrupt received")

                print("\n\nUse 'quit' command to shutdown gracefully.")
            except Exception as e:
                logging.error("Error in command handler: %s", e)

        logging.info("Command handler stopped")
