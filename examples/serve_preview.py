"""Serve the saved preview locally: python examples/serve_preview.py."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer


class PreviewServer(ThreadingHTTPServer):
    def server_bind(self):
        # Avoid reverse-DNS lookup on machines with a slow local resolver.
        TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


if __name__ == "__main__":
    directory = Path(__file__).resolve().parents[1] / "preview"
    server = PreviewServer(
        ("127.0.0.1", 8765), partial(SimpleHTTPRequestHandler, directory=str(directory))
    )
    print("Open http://127.0.0.1:8765/radiation_patterns.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
