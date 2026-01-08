# Multi-Server Python Application

A Python application that implements three servers: HTTP, WebSocket, and File servers, all configurable via a JSON configuration file.

## Features

### HTTP Server (Port 8080)
- **GET /**: Server information and available endpoints
- **GET /health**: Health check endpoint
- **POST /echo**: Echo back request body (JSON or text)

### WebSocket Server (Port 8081)
- **WS /ws**: WebSocket endpoint for real-time bidirectional communication
- Broadcasts messages to all connected clients
- Echoes messages back to sender
- Tracks active connections

### File Server (Port 8082)
- **GET /**: Server information and available endpoints
- **GET /list**: List all files in the root directory
- **GET /files/{path}**: Download/serve specific files
- **POST /upload**: Upload files (multipart/form-data)
- Serves files from configurable root directory (default: `./files`)

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Edit `config.json` to customize server settings:

```json
{
  "http_server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "websocket_server": {
    "host": "0.0.0.0",
    "port": 8081
  },
  "file_server": {
    "host": "0.0.0.0",
    "port": 8082,
    "root_directory": "./files"
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

## Usage

### Start the Application

```bash
python main.py
```

All three servers will start simultaneously. Press `Ctrl+C` to stop all servers gracefully.

### Testing the Servers

#### HTTP Server Examples

```bash
# Get server info
curl http://localhost:8080/

# Health check
curl http://localhost:8080/health

# Echo JSON
curl -X POST http://localhost:8080/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, World!"}'

# Echo text
curl -X POST http://localhost:8080/echo \
  -H "Content-Type: text/plain" \
  -d "Hello, World!"
```

#### WebSocket Server Examples

Using `wscat` (install with `npm install -g wscat`):

```bash
# Connect to WebSocket
wscat -c ws://localhost:8081/ws

# Send a message (after connecting)
> {"action": "ping", "data": "test"}

# Get server info via HTTP
curl http://localhost:8081/
```

#### File Server Examples

```bash
# Get server info
curl http://localhost:8082/

# List all files
curl http://localhost:8082/list

# Download a file
curl http://localhost:8082/files/example.txt

# Upload a file
curl -X POST http://localhost:8082/upload \
  -F "file=@/path/to/your/file.txt"
```

## Project Structure

```
.
├── main.py              # Main application with all server implementations
├── config.json          # Configuration file
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── files/              # File server root directory (created automatically)
```

## Requirements

- Python 3.7+
- aiohttp 3.9.1+

## Server Architecture

The application uses `aiohttp` for asynchronous HTTP and WebSocket handling:

- **ConfigLoader**: Loads and validates JSON configuration
- **HTTPServer**: Implements REST API endpoints
- **WebSocketServer**: Manages WebSocket connections and broadcasts
- **FileServer**: Serves static files with upload capability
- **MultiServerApp**: Orchestrates all servers and handles graceful shutdown

All servers run concurrently using Python's `asyncio` event loop.

## Logging

Logs are output to stdout with configurable level and format. Default level is INFO.

## Security Notes

- The file server implements path traversal protection
- For production use, consider adding authentication and HTTPS
- Bind to specific interfaces instead of 0.0.0.0 in production
- Implement rate limiting for upload endpoints

## License

This is a sample application for demonstration purposes.
