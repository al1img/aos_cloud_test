# GitHub Copilot Instructions for AOS Cloud Test Project

## Project Overview
This is a Python-based multi-server application that implements three concurrent servers:
- **HTTP Server**: REST API with health checks and echo endpoints
- **WebSocket Server**: Real-time bidirectional communication with broadcast capabilities
- **File Server**: File upload, download, and management system

The application is built with `aiohttp` for asynchronous server implementations and uses JSON-based configuration.

## Project Structure
- `main.py`: Entry point that orchestrates all three servers
- `http_server.py`: HTTP server implementation with REST endpoints
- `websocket_server.py`: WebSocket server for real-time communication
- `file_server.py`: File server for static file serving and uploads
- `config_loader.py`: Configuration management from `config.json`
- `config.json`: JSON configuration file for all servers (camelCase keys)
- `files/`: Directory for file server storage

## Code Style and Conventions

### Python Style
- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Use docstrings for all classes and public methods (Google style)
- Maximum line length: 120 characters (Black formatter compatible)
- add empty line before and after log except for the first line in the function
- add empty line before return, break, continue, pass statements except for the first line in the function
- use lazy formatting for log messages

### Naming Conventions
- **Classes**: PascalCase (e.g., `HTTPServer`, `WebSocketServer`)
- **Functions/Methods**: snake_case (e.g., `handle_root`, `setup_logging`)
- **Constants**: UPPER_SNAKE_CASE
- **Config keys**: camelCase in JSON (e.g., `httpServer`, `rootDirectory`)

### Async/Await Patterns
- All server methods should be async
- Use `asyncio` for concurrent operations
- Properly handle cleanup with try/finally blocks
- Use `async with` for context managers

### Error Handling
- Log errors using the configured logging system
- Return appropriate HTTP status codes (404, 500, etc.)
- Handle JSON decode errors gracefully
- Validate file paths to prevent directory traversal attacks

## Configuration Management
- Configuration is loaded from `config.json` via `ConfigLoader`
- Config uses camelCase keys (e.g., `httpServer`, `rootDirectory`)
- All servers accept config dict in constructor
- Default ports: HTTP=5555, WebSocket=5556, File=5557

## Server Implementation Guidelines

### HTTP Server
- Use `aiohttp.web` for routing
- Return JSON responses with `web.json_response()`
- Include service name and status in root endpoint
- Echo endpoint should handle both JSON and text

### WebSocket Server
- Maintain `self.clients` set for connected clients
- Send welcome message on connection
- Echo messages back to sender
- Broadcast to all clients when needed
- Clean up disconnected clients properly

### File Server
- Validate file paths to prevent directory traversal
- Create root directory if it doesn't exist
- Return proper Content-Type headers
- Handle multipart file uploads
- List files with metadata (path, size, modified time)

## Testing Suggestions
When implementing new features, suggest appropriate curl commands for HTTP/File server testing and wscat commands for WebSocket testing.

## Dependencies
- `aiohttp==3.9.1`: Core async web framework
- Keep dependencies minimal and well-maintained

## Logging
- Use Python's `logging` module configured in `main.py`
- Log level and format are configurable via `config.json`
- Include meaningful context in log messages
- Log server start/stop events and connections

## Common Tasks

### Adding New HTTP Endpoints
1. Add async handler method in `HTTPServer` class
2. Register route in `_setup_routes()` method
3. Include endpoint in root response
4. Add appropriate error handling

### Adding New WebSocket Message Types
1. Handle new message type in `websocket_handler()`
2. Implement message validation
3. Add appropriate response/broadcast logic
4. Log message processing

### Extending File Server
1. Add new handler in `FileServer` class
2. Validate paths and permissions
3. Register route in `_setup_routes()`
4. Update root endpoint documentation

## Security Considerations
- Validate all file paths to prevent directory traversal
- Sanitize user input before processing
- Use proper error messages that don't leak system info
- Implement rate limiting for production use
- Consider authentication for sensitive endpoints

## Best Practices
- Use context managers for resource management
- Properly close connections and cleanup resources
- Handle graceful shutdown with signal handlers
- Log errors with full context but sanitize sensitive data
- Write testable code with dependency injection
- Keep server classes focused and single-responsibility
