import base64
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request
from pathlib import Path

CH_API_BASE = "https://api.company-information.service.gov.uk"

def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def load_env_file():
    """Load .env file from project root"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"Loading environment from: {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
                    if key.strip() == "CH_API_KEY":
                        print(f"✓ CH_API_KEY loaded: {value.strip()[:8]}...")
    else:
        print(f"Warning: No .env file found at {env_path}")
        print("Set CH_API_KEY environment variable or create .env file")

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Proxy endpoints:
        # /ch/search/companies?q=...&items_per_page=...
        # /ch/company/{company_number}
        # /ch/company/{company_number}/persons-with-significant-control
        # /ch/search/officers?q=...&items_per_page=...
        if self.path.startswith("/ch/"):
            api_key = os.environ.get("CH_API_KEY", "").strip()
            if not api_key:
                print("ERROR: CH_API_KEY not found in environment")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"error":"CH_API_KEY env var not set"}')
                return

            upstream_url = CH_API_BASE + self.path.replace("/ch", "", 1)
            print(f"Proxying: {self.path} -> {upstream_url}")

            req = urllib.request.Request(upstream_url)
            req.add_header("Authorization", "Basic " + b64(f"{api_key}:"))
            req.add_header("Accept", "application/json")

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                    # Allow browser calls to this local server
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                    print(f"✓ Proxy success: {resp.status}")
            except urllib.error.HTTPError as e:
                print(f"✗ HTTP Error {e.code}: {e.reason}")
                body = e.read() if hasattr(e, 'read') else b'{}'
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                print(f"✗ Proxy error: {e}")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(("{\"error\":\"Upstream failed\",\"detail\":\"%s\"}" % str(e)).encode("utf-8"))
            return

        # Static files
        return super().do_GET()

def main():
    # Load .env file first
    load_env_file()
    
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"\n{'='*60}")
    print(f"🚀 Control Room Server Running")
    print(f"{'='*60}")
    print(f"Local:  http://localhost:{port}")
    print(f"Proxy:  /ch/* -> {CH_API_BASE}")
    print(f"{'='*60}\n")
    server.serve_forever()

if __name__ == "__main__":
    main()
