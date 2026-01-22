# AOS Cloud Test

A Python-based multi-server application designed for testing AOS (Automotive Operating System) cloud functionality. Implements HTTP, WebSocket, and File servers with interactive command-line interface for testing and interaction.

## Features

### HTTP Server (Default Port: 5555)

- **POST /sd/v7/**: Service discovery endpoint
  - Returns WebSocket connection information
  - Provides version and connection details for client discovery

### WebSocket Server (Default Port: 5556)

- **GET /**: Server status and active connections info
- **WS /ws**: WebSocket endpoint for real-time bidirectional communication
  - Custom binary message protocol (UTF-8 encoded JSON)
  - Automatic message acknowledgment (ACK)
  - System ID based client tracking
  - Message types:
    - `requestBlobUrls`: Request file blob URLs and metadata
    - `blobUrls`: Response with file URLs, checksums, and sizes
    - `ack`: Message acknowledgment
  - Structured message format with headers (version, systemId, txn)

### File Server (Default Port: 5557)

- **GET /**: Server information and available endpoints
- **GET /list**: List all files with metadata (path, size, modified time)
- **GET /files/{path}**: Download/serve specific files
  - Supports nested directory structure (e.g., `/files/sha256/<hash>`)
  - Path traversal protection
- **POST /upload**: Upload files (multipart/form-data)
- Blob management with SHA256 verification
- Serves files from configurable root directory (default: `./files`)

### Interactive Command Handler

- **help**: Display all available commands
- **test <param1> <param2>**: Test command with parameter validation
- **send <file_path>**: Read JSON file and send via WebSocket
- **quit**: Gracefully shutdown the application
- Command history with readline support
- Tab completion for command names
- Persistent command history (saved to `.aos_cloud_test_history`)

## Installation

1. **Clone the repository** (if applicable)

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Prepare configuration:**
   - Edit `config.json` to customize server settings (optional)
   - Default configuration uses localhost ports 5555-5557

## Configuration

Edit `config.json` to customize server settings:

```json
{
  "httpServer": {
    "host": "10.0.0.1",
    "port": 5555
  },
  "websocketServer": {
    "host": "10.0.0.1",
    "port": 5556
  },
  "fileServer": {
    "host": "10.0.0.1",
    "port": 5557,
    "rootDirectory": "./files"
  },
  "itemsPath": "./items",
  "messagesPath": "./messages",
  "logging": {
    "level": "DEBUG",
    "uvicornLevel": "WARNING",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

### Configuration Options

- **httpServer**: HTTP server configuration
  - `host`: Bind address (use "0.0.0.0" for all interfaces)
  - `port`: HTTP server port
- **websocketServer**: WebSocket server configuration
  - `host`: Bind address
  - `port`: WebSocket server port
- **fileServer**: File server configuration
  - `host`: Bind address
  - `port`: File server port
  - `rootDirectory`: Directory for file storage (created automatically)
- **itemsPath**: Path to items directory containing service configurations (default: `./items`)
- **messagesPath**: Path to messages directory for updating index digests (default: `./messages`)
- **logging**: Logging configuration
  - `level`: Application log level (DEBUG, INFO, WARNING, ERROR)
  - `uvicornLevel`: Uvicorn server log level (separate from application logs)
  - `format`: Log message format string

## Usage

### Start the Application

```bash
python -m src.main
```

All three servers will start simultaneously in separate threads, and an interactive command prompt will appear. Type `help` to see available commands.

### Interactive Commands

Once the application is running, you can use these commands:

```bash
# Display help
help

# Send JSON message from file via WebSocket
send messages/desiredstatus.json

# Change log level at runtime
loglevel DEBUG
loglevel INFO
loglevel WARNING
loglevel ERROR

# Update OCI blobs from items directory
update

# Quit application
quit
```

**Available Commands:**

- **help**: Display all available commands with their arguments and descriptions
- **send <file_path>**: Read a JSON file and send its content via WebSocket to connected units
  - Example: `send messages/desiredstatus.json`
  - The file should contain a valid JSON message with proper header and data structure
- **loglevel <level>**: Change the application log level at runtime
  - Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Example: `loglevel DEBUG` to enable verbose logging
  - Useful for debugging without restarting the application
- **update**: Process items and generate OCI-compliant blobs
  - Reads `config.yaml` from each item directory in `items/` path
  - Generates OCI blobs (layers, manifests, configs) dynamically from YAML configuration
  - Creates separate index blob for each item defined in the YAML
  - Updates `desiredStatus` messages in `messages/` directory with corresponding index digests
  - Verifies existing blobs by checksum (1MB chunks) before overwriting
  - Preserves JSON key order in generated blobs
  - Clears and rebuilds the entire `files/sha256/` directory
  - Useful for deploying new service versions or updating configurations
- **quit**: Gracefully shutdown the application and all servers

**Command Features:**

- Tab completion for command names
- Command history (up/down arrows)
- Persistent history saved to `.aos_cloud_test_history`
- Ctrl+C shows shutdown hint (use `quit` for graceful shutdown)
- Ctrl+D (EOF) exits the application

### Testing the Servers

#### HTTP Server Examples

```bash
# Service discovery
curl -X POST http://localhost:5555/sd/v7/ \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected response:
# {
#   "version": 7,
#   "connectionInfo": ["ws://localhost:5556/ws"],
#   "errorCode": 0
# }
```

#### WebSocket Server Examples

**Using wscat** (install with `npm install -g wscat`):

```bash
# Connect to WebSocket
wscat -c ws://localhost:5556/ws

# Check server status via HTTP
curl http://localhost:5556/
```

**WebSocket Message Format:**

Messages use a structured JSON format with headers:

```json
{
  "header": {
    "version": 7,
    "systemId": "your-system-id",
    "txn": "unique-transaction-id"
  },
  "data": {
    "messageType": "requestBlobUrls",
    "correlationId": "correlation-id",
    "digests": ["sha256:b94f7c829fcf8166c9cc83da53fc11eaaacfaeaf7e4874fa5015d7d51cdd0ae7"]
  }
}
```

**Request Blob URLs Example:**

```json
{
  "header": {
    "version": 7,
    "systemId": "test-system",
    "txn": "txn-001"
  },
  "data": {
    "messageType": "requestBlobUrls",
    "correlationId": "corr-001",
    "digests": ["sha256:<hash>"]
  }
}
```

Response will include:

```json
{
  "header": { ... },
  "data": {
    "messageType": "blobUrls",
    "correlationId": "corr-001",
    "items": [{
      "digest": "sha256:<hash>",
      "urls": ["http://localhost:5557/files/sha256/<hash>"],
      "sha256": "<calculated-hash>",
      "size": 1234
    }]
  }
}
```

#### File Server Examples

```bash
# Get server info
curl http://localhost:5557/

# List all files with metadata
curl http://localhost:5557/list

# Download a file
curl http://localhost:5557/files/sha256/b94f7c829fcf8166c9cc83da53fc11eaaacfaeaf7e4874fa5015d7d51cdd0ae7

# Upload a file
curl -X POST http://localhost:5557/upload \
  -F "file=@/path/to/your/file.txt"

# Upload multiple files
curl -X POST http://localhost:5557/upload \
  -F "file=@file1.txt" \
  -F "file=@file2.txt"
```

## Project Structure

```console
.
├── src/                       # Source code directory
│   ├── __init__.py            # Package initialization
│   ├── main.py                # Main application orchestrating all servers
│   ├── http_server.py         # HTTP server implementation (FastAPI)
│   ├── websocket_server.py    # WebSocket server implementation (FastAPI)
│   ├── file_server.py         # File server with blob management (FastAPI)
│   ├── command_handler.py     # Interactive command-line interface
│   └── config_loader.py       # Configuration management
├── config.json                # JSON configuration file (camelCase keys)
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Python project metadata and build config
├── README.md                  # This file
├── files/                     # File server root directory (auto-created)
│   └── sha256/                # SHA256 algorithm directory
│       └── <hash>             # Files stored by hash
├── items/                     # Service items with config.yaml files
│   └── demo_service/          # Demo service directory
│       ├── config.yaml        # Item configuration (YAML format)
│       └── rootfs/            # Service rootfs directory
│           └── demo_service/  # Service files
└── messages/                  # Message files for WebSocket communication
    └── desiredstatus.json     # Example desiredStatus message
```

## Requirements

- **Python 3.8+**
- **FastAPI**: Modern web framework for APIs
- **Uvicorn**: ASGI server for FastAPI applications
- **python-multipart**: For file upload handling
- **websockets**: WebSocket support for FastAPI
- **PyYAML**: YAML configuration file parsing

See `requirements.txt` for specific versions.

## Item Configuration Format

The `update` command processes `config.yaml` files from the items directory to generate OCI-compliant blobs. Each item configuration defines service metadata, images, and runtime settings.

### config.yaml Structure

```yaml
schemaVersion: 2
publisher:
  author: Your Name
  company: EPAM Systems
items:
  - identity:
      id: 4e28eb0f-a1cf-4112-8b67-7543bee166db  # Unique item ID (UUID)
      codename: demo_service
      type: service
    version: 1.0.0
    images:
      - source_folder: rootfs           # Directory containing service files
        os_info:
          os: linux
        arch_info:
          architecture: amd64
        work_dir: /
        cmd: ["python3", "/demo_service/demo_service.py"]
    configuration:
      runtimes: ["runc", "crun"]
      quotas:
        cpu_limit: 1000                 # CPU limit in DMIPS
        ram_limit: 8192000              # RAM limit in bytes
        storage_limit: 8192000          # Storage limit in bytes
```

### Generated Blobs

For each item, the `update` command generates:

1. **Layer blobs**: Compressed tar.gz archives of rootfs directories
   - Stored with SHA256 hash as filename
   - Includes both compressed and uncompressed hashes
2. **Image config blob**: OCI image configuration JSON
   - Architecture, OS, entrypoint, working directory
   - Rootfs diff_ids for layer verification
3. **Service config blob**: AOS-specific service configuration
   - Runtime preferences (runc, crun, etc.)
   - Resource quotas (CPU, RAM, storage)
4. **Manifest blob**: OCI manifest linking configs and layers
   - References all blobs by digest
   - Proper mediaType for each component
5. **Index blob**: OCI index for the item
   - One index per item (even if multiple items in same config.yaml)
   - Contains references to all manifests for that item

### Message Updates

The `update` command automatically updates `desiredStatus` messages in the `messages/` directory:

- Matches items by their identity ID
- Updates the `indexDigest` field with the newly generated index blob digest
- Preserves all other message fields
- Only updates messages with `messageType: "desiredStatus"`

Example desiredStatus message structure:

```json
{
  "messageType": "desiredStatus",
  "items": [
    {
      "item": {
        "id": "4e28eb0f-a1cf-4112-8b67-7543bee166db",
        "type": "service"
      },
      "version": "1.0.0",
      "owner": {
        "id": "638d25c4-e80d-4486-81a5-42008214b0dc",
        "type": "sp"
      },
      "indexDigest": "sha256:54c845a26c95043580a735648fde9acaf898c1742c2e2c034aaef90f509425bc"
    }
  ]
}
```

## Server Architecture

The application uses **FastAPI** with **Uvicorn** for high-performance asynchronous server implementations:

- **AosCloud**: Main application class that orchestrates all servers
- **ConfigLoader**: Loads and validates JSON configuration (camelCase keys)
- **HTTPServer**: Implements service discovery endpoint using FastAPI
- **WebSocketServer**: Manages WebSocket connections with custom binary protocol
- **FileServer**: Serves static files with blob management and upload capability
- **CommandHandler**: Interactive CLI with readline support and command history

### Threading Model

- Each server runs in its own daemon thread
- All servers use asynchronous I/O via FastAPI/Uvicorn
- Main thread runs the command handler in an asyncio event loop
- Graceful shutdown triggered by `quit` command or EOF

### Message Protocol

WebSocket messages use a structured format:

1. **Binary transport**: UTF-8 encoded JSON sent as bytes
2. **Header structure**: version, systemId, txn (transaction ID)
3. **Data payload**: messageType-specific content
4. **Automatic ACK**: Server acknowledges all non-ACK messages

## Logging

Logs are output to stdout with configurable level and format:

- **Application logs**: Controlled by `logging.level` in config
- **Uvicorn logs**: Separately controlled by `logging.uvicornLevel`
- **Log levels**: DEBUG, INFO, WARNING, ERROR
- **Includes**: Timestamps, logger names, levels, and messages

Example log output:

```console
2026-01-09 10:30:15,123 - root - INFO - Start Aos test cloud
2026-01-09 10:30:15,234 - root - INFO - Start HTTP Server on http://10.0.0.1:5555
2026-01-09 10:30:15,345 - root - INFO - Start WebSocket Server on ws://10.0.0.1:5556/ws
2026-01-09 10:30:15,456 - root - INFO - Start File Server on http://10.0.0.1:5557
```

## Development Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Maximum line length: 120 characters (Black formatter compatible)
- Use docstrings for all classes and public methods (Google style)

### Naming Conventions

- **Classes**: PascalCase (e.g., `HTTPServer`, `WebSocketServer`)
- **Functions/Methods**: snake_case (e.g., `handle_root`, `send_message`)
- **Constants**: UPPER_SNAKE_CASE
- **Config keys**: camelCase in JSON (e.g., `httpServer`, `rootDirectory`)

### Adding New Commands

To add a new interactive command:

1. Create a new command class inheriting from `Command` in `src/command_handler.py`
2. Implement required properties: `name`, `help_args`, `help`
3. Implement `async execute(self, args, context)` method
4. Register the command in `CommandHandler._register_commands()`

Example:

```python
class MyCommand(Command):
    @property
    def name(self) -> str:
        return "mycommand"
    
    @property
    def help_args(self) -> str:
        return "<arg1>"
    
    @property
    def help(self) -> str:
        return "Description of my command"
    
    async def execute(self, args: List[str], context: Dict[str, Any]):
        # Implementation here
        pass
```

## Security Notes

- **Path Traversal Protection**: File server validates all paths to prevent directory traversal attacks
- **Input Validation**: WebSocket messages are validated before processing
- **Production Considerations**:
  - Add authentication for sensitive endpoints
  - Implement HTTPS/WSS for encrypted communication
  - Use specific bind addresses instead of 0.0.0.0
  - Implement rate limiting for upload endpoints
  - Add request size limits
  - Implement proper error handling without information leakage

## Troubleshooting

### Port Already in Use

If you see "Address already in use" errors:

```console
# Find process using the port (example for port 5555)
lsof -i :5555

# Kill the process
kill -9 <PID>
```

### WebSocket Connection Issues

- Verify the server is running: `curl http://localhost:5556/`
- Check firewall settings if connecting from remote machine
- Ensure client uses correct WebSocket URL format: `ws://host:port/ws`

### File Upload Failures

- Check `rootDirectory` exists and has write permissions
- Verify file size doesn't exceed limits
- Ensure proper Content-Type header: `multipart/form-data`

### Command History Not Working

- Ensure readline is installed: `pip install readline` (Unix/Linux)
- Check `.aos_cloud_test_history` file permissions

## Testing

### Manual Testing Workflow

1. Start the application: `python -m src.main`
2. In another terminal, test HTTP endpoint:

   ```console
   curl -X POST http://localhost:5555/sd/v7/ -H "Content-Type: application/json" -d '{}'
   ```

3. Test file upload:

   ```console
   echo "test content" > test.txt
   curl -X POST http://localhost:5557/upload -F "file=@test.txt"
   ```

4. Test WebSocket with sample message:

   ```console
   send messages/desiredstatus.json
   ```

5. Verify file listing:

   ```console
   curl http://localhost:5557/list
   ```

## License

This is a test application for AOS cloud functionality development and testing purposes.

## Contributing

When contributing to this project:

1. Follow the code style guidelines in `.github/copilot-instructions.md`
2. Add appropriate logging for new features
3. Update this README if adding new functionality
4. Test all three servers after changes
5. Use present simple tense in method names and log messages
