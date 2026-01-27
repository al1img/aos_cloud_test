import http.server
import json


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "ok", "service": "server_service"}
        self.wfile.write(json.dumps(response).encode())


def main():
    server = http.server.HTTPServer(("0.0.0.0", 30001), Handler)
    print("Server service started on port 30001")
    server.serve_forever()


if __name__ == "__main__":
    main()
