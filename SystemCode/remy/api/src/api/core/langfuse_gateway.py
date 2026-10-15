"""Localhost-only, passwordless dashboard gateway using Langfuse's native session."""

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import httpx

UPSTREAM = "http://langfuse-web:3000"
MAX_BODY = 16 * 1024 * 1024
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade"}
_lock = threading.Lock()
_cookie, _expires = "", 0.0


def session_cookie():
    global _cookie, _expires
    with _lock:
        if _cookie and time.monotonic() < _expires:
            return _cookie
        email, password = os.environ["LANGFUSE_INIT_USER_EMAIL"], os.environ["LANGFUSE_INIT_USER_PASSWORD"]
        with httpx.Client(base_url=UPSTREAM, timeout=30, trust_env=False) as client:
            csrf = client.get("/api/auth/csrf")
            csrf.raise_for_status()
            login = client.post("/api/auth/callback/credentials", data={
                "csrfToken": csrf.json()["csrfToken"], "email": email, "password": password,
                "callbackUrl": "/", "json": "true",
            })
            login.raise_for_status()
            session = client.get("/api/auth/session")
            session.raise_for_status()
            if session.json().get("user", {}).get("email") != email:
                raise RuntimeError("Local dashboard session could not be established")
            _cookie = "; ".join(f"{c.name}={c.value}" for c in client.cookies.jar
                                if "next-auth.session-token" in c.name)
            if not _cookie:
                raise RuntimeError("Local dashboard session cookie missing")
            _expires = time.monotonic() + 600
            return _cookie


class Gateway(BaseHTTPRequestHandler):
    # ponytail: HTTP proxy, not WebSockets; add websocket support only if dashboard features require it.
    def proxy(self):
        self.connection.settimeout(30)
        if not self.path.startswith("/") or self.path.startswith("//"):
            self.send_error(400, "Relative paths only")
            return
        dashboard = urlsplit(os.environ["LANGFUSE_DASHBOARD_URL"])
        origins = {f"http://{host}:{dashboard.port}" for host in ("localhost", "127.0.0.1", "[::1]")}
        hosts = {urlsplit(origin).netloc for origin in origins}
        health = self.path == "/health" and self.command == "GET"
        if not health:
            if self.headers.get("Host") not in hosts:
                self.send_error(403, "Local dashboard host required")
                return
            origin = self.headers.get("Origin")
            cross_site = self.headers.get("Sec-Fetch-Site") == "cross-site"
            navigation = self.command == "GET" and self.headers.get("Sec-Fetch-Mode") == "navigate"
            if (origin and origin not in origins) or (cross_site and not navigation):
                self.send_error(403, "Cross-origin dashboard access denied")
                return
        if self.headers.get("Transfer-Encoding"):
            self.send_error(411, "Content-Length required")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if not 0 <= length <= MAX_BODY:
            self.send_error(413, "Request body too large")
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.send_error(400, "Incomplete request body")
            return
        headers = httpx.Headers({key: value for key, value in self.headers.items()
                                 if key.lower() not in HOP_HEADERS | {"host", "content-length"}
                                 and not key.lower().startswith("x-forwarded-")})
        headers["Host"] = dashboard.netloc
        headers["X-Forwarded-Proto"] = "http"
        path = "/api/public/health" if health else self.path
        sent = False
        try:
            if not path.startswith("/api/public/"):
                browser_cookies = [c.strip() for c in headers.pop("Cookie", "").split(";")
                                   if c.strip() and "next-auth.session-token" not in c.split("=", 1)[0]]
                headers["Cookie"] = "; ".join(browser_cookies + [session_cookie()])
            with httpx.Client(base_url=UPSTREAM, timeout=30, trust_env=False) as client:
                with client.stream(self.command, path, headers=headers, content=body) as response:
                    self.send_response(response.status_code)
                    for key, value in response.headers.multi_items():
                        if key.lower() not in HOP_HEADERS | {"x-frame-options"} and not key.lower().startswith("access-control-"):
                            self.send_header(key, value)
                    self.send_header("X-Frame-Options", "DENY")
                    self.end_headers()
                    sent = True
                    if self.command != "HEAD":
                        for chunk in response.iter_raw():
                            self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            # Never expose cookies, credentials, or upstream request details.
            if not sent:
                self.send_error(502, "Local Langfuse session/upstream unavailable")
            else:
                self.close_connection = True

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = proxy

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    for key in ("LANGFUSE_DASHBOARD_URL", "LANGFUSE_INIT_USER_EMAIL", "LANGFUSE_INIT_USER_PASSWORD"):
        if not os.getenv(key):
            raise RuntimeError(f"Required local gateway setting missing: {key}")
    ThreadingHTTPServer(("0.0.0.0", 3030), Gateway).serve_forever()
