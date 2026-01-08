"""File server implementation."""

import logging
from pathlib import Path
from typing import Any, Dict

from aiohttp import web


class FileServer:
    """File server for serving static files."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = web.Application()
        self.root_dir = Path(config["fileServer"]["rootDirectory"])
        self._setup_directory()
        self._setup_routes()

    async def handle_root(self, request: web.Request) -> web.Response:
        """Handle root endpoint."""
        return web.json_response(
            {
                "service": "File Server",
                "status": "running",
                "root_directory": str(self.root_dir.absolute()),
                "endpoints": ["/", "/list", "/files/{path}", "/upload"],
            }
        )

    async def handle_list(self, request: web.Request) -> web.Response:
        """List all files in the root directory."""
        files = []
        for item in self.root_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(self.root_dir)
                files.append(
                    {
                        "path": str(rel_path),
                        "size": item.stat().st_size,
                        "modified": item.stat().st_mtime,
                    }
                )

        return web.json_response({"files": files})

    async def handle_file(self, request: web.Request) -> web.Response:
        """Serve a specific file."""
        file_path = request.match_info["path"]
        full_path = (self.root_dir / file_path).resolve()

        # Security check: ensure path is within root directory
        try:
            full_path.relative_to(self.root_dir.resolve())
        except ValueError:
            return web.json_response({"error": "Access denied"}, status=403)

        if not full_path.exists():
            return web.json_response({"error": "File not found"}, status=404)

        if not full_path.is_file():
            return web.json_response({"error": "Not a file"}, status=400)

        return web.FileResponse(full_path)

    async def handle_upload(self, request: web.Request) -> web.Response:
        """Handle file upload."""
        reader = await request.multipart()

        uploaded_files = []
        async for field in reader:
            if field.filename:
                filename = field.filename
                filepath = self.root_dir / filename

                # Write file
                with open(filepath, "wb") as f:
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break

                        f.write(chunk)

                uploaded_files.append(
                    {"filename": filename, "size": filepath.stat().st_size}
                )

                logging.info("File uploaded: %s", filename)

        return web.json_response(
            {"message": "Upload successful", "files": uploaded_files}
        )

    async def start(self):
        """Start the file server."""
        host = self.config["fileServer"]["host"]
        port = self.config["fileServer"]["port"]

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        logging.info("File Server started on http://%s:%s", host, port)

        return runner

    def _setup_directory(self):
        """Ensure the root directory exists."""
        self.root_dir.mkdir(parents=True, exist_ok=True)

        logging.info("File server root directory: %s", self.root_dir.absolute())

    def _setup_routes(self):
        """Setup file server routes."""
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/list", self.handle_list)
        self.app.router.add_get("/files/{path:.*}", self.handle_file)
        self.app.router.add_post("/upload", self.handle_upload)
