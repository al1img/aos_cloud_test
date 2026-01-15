"""Command handler for console input."""

import asyncio
import copy
import hashlib
import json
import logging
import os
import readline
import rlcompleter
import shutil
import tarfile
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
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
            raise ValueError("send command requires a file path")

        file_path = args[0]

        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a file: {file_path}")

        websocket_server = context.get("websocket_server")

        if not websocket_server:
            raise RuntimeError("WebSocket server not available")

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

            raise

        except Exception as e:
            logging.error("Error reading or sending file: %s", e)

            raise


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


class UpdateCommand(Command):
    """Update OCI blobs from items."""

    @property
    def name(self) -> str:
        return "update"

    @property
    def help_args(self) -> str:
        return ""

    @property
    def help(self) -> str:
        return "Clear file server and convert items to OCI blobs"

    async def execute(self, args: List[str], context: Dict[str, Any]):
        """
        Clear file server root directory and convert items to OCI blobs.

        Args:
            args: Command arguments (none expected)
            context: Context with server references
        """
        config = context.get("config", {})
        items_path = config.get("itemsPath", "./items")
        root_directory = config.get("fileServer", {}).get("rootDirectory", "./files")

        # Clear root directory
        logging.info("Clear file server root directory: %s", root_directory)

        if os.path.exists(root_directory):
            shutil.rmtree(root_directory)

        # Create sha256 directory for blobs
        sha256_dir = os.path.join(root_directory, "sha256")
        os.makedirs(sha256_dir, exist_ok=True)

        # Process items
        if not os.path.exists(items_path):
            raise FileNotFoundError(f"Items path not found: {items_path}")

        items_processed = 0
        blobs_created = 0

        for item_name in os.listdir(items_path):
            item_dir = os.path.join(items_path, item_name)

            if not os.path.isdir(item_dir):
                continue

            logging.info("Process item: %s", item_name)

            print(f"Processing item: {item_name}")

            # Read index.json
            index_path = os.path.join(item_dir, "index.json")

            if not os.path.exists(index_path):
                logging.warning("Skip item %s: index.json not found", item_name)

                continue

            with open(index_path, "r", encoding="utf-8") as f:
                original_index_data = json.load(f)

            index_data = copy.deepcopy(original_index_data)
            # Remove digest field if present (should not be in deployed index)
            if "digest" in index_data:
                del index_data["digest"]

            # Process each manifest in the index
            for manifest_entry in index_data.get("manifests", []):
                manifest_path = os.path.join(item_dir, manifest_entry.get("path", ""))

                if not os.path.exists(manifest_path):
                    logging.warning("Skip manifest: %s not found", manifest_path)

                    continue

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)

                logging.info("Process manifest: %s", manifest_entry.get("path"))

                # Process config (image.json)
                if "config" in manifest_data:
                    config_entry = manifest_data["config"]
                    config_path = os.path.join(item_dir, config_entry.get("path", ""))

                    if os.path.exists(config_path):
                        blob_hash, blob_size = await self._deploy_blob(config_path, sha256_dir)

                        logging.info("Create config blob: %s", blob_hash)

                        # Update manifest with digest and size
                        manifest_data["config"]["digest"] = f"sha256:{blob_hash}"
                        manifest_data["config"]["size"] = blob_size
                        del manifest_data["config"]["path"]

                        blobs_created += 1

                # Process aosService (service.json)
                if "aosService" in manifest_data:
                    service_entry = manifest_data["aosService"]
                    service_path = os.path.join(item_dir, service_entry.get("path", ""))

                    if os.path.exists(service_path):
                        blob_hash, blob_size = await self._deploy_blob(service_path, sha256_dir)

                        logging.info("Create aosService blob: %s", blob_hash)

                        # Update manifest with digest and size
                        manifest_data["aosService"]["digest"] = f"sha256:{blob_hash}"
                        manifest_data["aosService"]["size"] = blob_size
                        del manifest_data["aosService"]["path"]

                        blobs_created += 1

                # Process layers (rootfs)
                for layer in manifest_data.get("layers", []):
                    layer_path = os.path.join(item_dir, layer.get("path", ""))

                    if os.path.exists(layer_path):
                        if os.path.isdir(layer_path):
                            # Compress directory to tar.gz
                            blob_hash, blob_size = await self._deploy_layer_blob(layer_path, sha256_dir)

                            logging.info("Create layer blob: %s", blob_hash)

                        else:
                            # Single file layer
                            blob_hash, blob_size = await self._deploy_blob(layer_path, sha256_dir)

                            logging.info("Create layer blob: %s", blob_hash)

                        # Update layer with digest and size
                        layer["digest"] = f"sha256:{blob_hash}"
                        layer["size"] = blob_size
                        del layer["path"]

                        blobs_created += 1

                # Deploy modified manifest
                manifest_blob_hash, manifest_blob_size = await self._deploy_spec(manifest_data, sha256_dir)

                logging.info("Deploy manifest blob: %s", manifest_blob_hash)

                # Update index entry with manifest digest and size
                manifest_entry["digest"] = f"sha256:{manifest_blob_hash}"
                manifest_entry["size"] = manifest_blob_size
                del manifest_entry["path"]

                blobs_created += 1

            # Deploy modified index (without digest field)
            index_blob_hash, _ = await self._deploy_spec(index_data, sha256_dir)

            logging.info("Deploy index blob: %s", index_blob_hash)

            blobs_created += 1

            # Add digest field to original index.json file
            original_index_data["digest"] = f"sha256:{index_blob_hash}"

            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(original_index_data, f, indent=4)

            logging.info("Update index.json with digest field")

            items_processed += 1

            print("\nUpdate complete:")
            print(f"  Items processed: {items_processed}")
            print(f"  Blobs created: {blobs_created}")

            logging.info("Update complete: %d items, %d blobs", items_processed, blobs_created)

    async def _deploy_blob(self, file_path: str, dst_dir: str) -> tuple[str, int]:
        """
        Create a blob from a file.

        Args:
            file_path: Path to source file
            sha256_dir: Directory to store blobs
            is_json: Whether the file is JSON (for pretty formatting)

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        with open(file_path, "rb") as f:
            content = f.read()

        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        blob_size = len(content)

        # Write blob
        blob_path = os.path.join(dst_dir, sha256_hash)

        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size

    async def _deploy_layer_blob(self, dir_path: str, dst_dir: str) -> tuple[str, int]:
        """
        Create a compressed tar.gz blob from a directory.

        Args:
            dir_path: Path to source directory
            dst_dir: Directory to store blobs

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        # Create temporary tar.gz file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Create tar.gz archive
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(dir_path, arcname=os.path.basename(dir_path))

            # Read compressed content
            with open(tmp_path, "rb") as f:
                content = f.read()

            # Calculate SHA256
            sha256_hash = hashlib.sha256(content).hexdigest()
            blob_size = len(content)

            # Write blob
            blob_path = os.path.join(dst_dir, sha256_hash)

            with open(blob_path, "wb") as f:
                f.write(content)

            return sha256_hash, blob_size

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _deploy_spec(self, spec_data: dict, dst_dir: str) -> tuple[str, int]:
        """
        Deploy a spec by creating a blob from the modified spec.

        Args:
            spec_data: Modified spec dictionary
            dst_dir: Directory to store blobs

        Returns:
            Tuple of (SHA256 hash, blob size in bytes)
        """
        # Serialize manifest to JSON
        spec_json = json.dumps(spec_data, indent=4)
        content = spec_json.encode("utf-8")

        # Calculate SHA256
        sha256_hash = hashlib.sha256(content).hexdigest()
        blob_size = len(content)

        # Write blob
        blob_path = os.path.join(dst_dir, sha256_hash)

        with open(blob_path, "wb") as f:
            f.write(content)

        return sha256_hash, blob_size


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
