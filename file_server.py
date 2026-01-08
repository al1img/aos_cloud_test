"""File server implementation."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse


class FileServer:
    """File server for serving static files."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = FastAPI()
        self.root_dir = Path(config["fileServer"]["rootDirectory"])
        self._setup_directory()
        self._setup_routes()

    async def handle_root(self) -> JSONResponse:
        """Handle root endpoint."""
        return JSONResponse(
            content={
                "service": "File Server",
                "status": "running",
                "root_directory": str(self.root_dir.absolute()),
                "endpoints": ["/", "/list", "/files/{path}", "/upload"],
            }
        )

    async def handle_list(self) -> JSONResponse:
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

        return JSONResponse(content={"files": files})

    async def handle_file(self, path: str) -> FileResponse:
        """Serve a specific file."""
        full_path = (self.root_dir / path).resolve()

        # Security check: ensure path is within root directory
        try:
            full_path.relative_to(self.root_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")

        return FileResponse(full_path)

    async def handle_upload(self, files: List[UploadFile] = File(...)) -> JSONResponse:
        """Handle file upload."""
        uploaded_files = []

        for file in files:
            if file.filename:
                filepath = self.root_dir / file.filename

                # Write file
                with open(filepath, "wb") as f:
                    content = await file.read()
                    f.write(content)

                uploaded_files.append(
                    {"filename": file.filename, "size": filepath.stat().st_size}
                )

                logging.info("File uploaded: %s", file.filename)

        return JSONResponse(
            content={"message": "Upload successful", "files": uploaded_files}
        )

    def start(self):
        """Start the file server."""
        host = self.config["fileServer"]["host"]
        port = self.config["fileServer"]["port"]

        logging.info("File Server started on http://%s:%s", host, port)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_config=None,  # Disable uvicorn's logging to use our own
        )

    def _setup_directory(self):
        """Ensure the root directory exists."""
        self.root_dir.mkdir(parents=True, exist_ok=True)

        logging.info("File server root directory: %s", self.root_dir.absolute())

    def _setup_routes(self):
        """Setup file server routes."""
        self.app.get("/")(self.handle_root)
        self.app.get("/list")(self.handle_list)
        self.app.get("/files/{path:path}")(self.handle_file)
        self.app.post("/upload")(self.handle_upload)
