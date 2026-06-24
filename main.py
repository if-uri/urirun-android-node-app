from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


APP_VERSION = "0.3.0"
DEFAULT_PORT = int(os.environ.get("URIRUN_ANDROID_APP_PORT", "8765"))
TERMUX_HOME = "/data/data/com.termux/files/home"
TERMUX_RUN_SCRIPT = os.environ.get(
    "URIRUN_TERMUX_RUN_SCRIPT",
    os.path.join(TERMUX_HOME, ".urirun-node", "run-node.sh"),
)
TERMUX_BASH = os.environ.get(
    "URIRUN_TERMUX_BASH",
    "/data/data/com.termux/files/usr/bin/bash",
)

ROUTES = [
    {"uri": "android://device/app/query/status", "kind": "query", "title": "Android app status"},
    {"uri": "android://device/app/query/routes", "kind": "query", "title": "List app URI routes"},
    {"uri": "android://device/app/query/log", "kind": "query", "title": "Recent app events"},
    {"uri": "android://device/app/command/ping", "kind": "command", "title": "Ping the app"},
    {"uri": "android://device/termux/query/status", "kind": "query", "title": "Termux node status"},
    {"uri": "android://device/termux/command/start", "kind": "command", "title": "Start Termux urirun node"},
    {"uri": "android://device/termux/command/stop", "kind": "command", "title": "Stop Termux urirun node"},
]


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class UriRuntime:
    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port
        self.started_at = time.time()
        self.events: list[dict[str, Any]] = []
        self.termux_proc: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def log(self, event: str, **detail: Any) -> None:
        row = {"ts": time.time(), "event": event, **detail}
        with self.lock:
            self.events.append(row)
            self.events = self.events[-80:]

    def termux_running(self) -> bool:
        return self.termux_proc is not None and self.termux_proc.poll() is None

    def status(self) -> dict[str, Any]:
        ip = lan_ip()
        return {
            "ok": True,
            "name": "android-device",
            "version": APP_VERSION,
            "nodeType": "android-app",
            "ip": ip,
            "url": f"http://{ip}:{self.port}",
            "uptimeSeconds": round(time.time() - self.started_at, 3),
            "routeCount": len(ROUTES),
            "termux": {
                "running": self.termux_running(),
                "bash": TERMUX_BASH,
                "runScript": TERMUX_RUN_SCRIPT,
                "runScriptExists": os.path.exists(TERMUX_RUN_SCRIPT),
            },
        }

    def start_termux(self) -> dict[str, Any]:
        if self.termux_running():
            return {"ok": True, "alreadyRunning": True, "termux": self.status()["termux"]}
        if not os.path.exists(TERMUX_BASH):
            return {"ok": False, "error": f"Termux bash not found: {TERMUX_BASH}"}
        if not os.path.exists(TERMUX_RUN_SCRIPT):
            return {"ok": False, "error": f"Termux urirun script not found: {TERMUX_RUN_SCRIPT}"}
        try:
            self.termux_proc = subprocess.Popen(
                [TERMUX_BASH, TERMUX_RUN_SCRIPT],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        self.log("termux-started", pid=self.termux_proc.pid)
        return {"ok": True, "pid": self.termux_proc.pid, "termux": self.status()["termux"]}

    def stop_termux(self) -> dict[str, Any]:
        if not self.termux_running():
            self.termux_proc = None
            return {"ok": True, "alreadyStopped": True}
        pid = self.termux_proc.pid
        self.termux_proc.terminate()
        self.termux_proc = None
        self.log("termux-stopped", pid=pid)
        return {"ok": True, "pid": pid}

    def handle_uri(self, uri: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        parsed = urlparse(uri)
        route = f"{parsed.netloc}{parsed.path}".strip("/")
        self.log("run", uri=uri)
        if parsed.scheme != "android":
            return {"ok": False, "error": f"unsupported scheme: {parsed.scheme}", "uri": uri}
        if route == "device/app/query/status":
            return self.status()
        if route == "device/app/query/routes":
            return {"ok": True, "routes": ROUTES}
        if route == "device/app/query/log":
            return {"ok": True, "events": list(self.events)}
        if route == "device/app/command/ping":
            return {"ok": True, "pong": True, "payload": payload, "status": self.status()}
        if route == "device/termux/query/status":
            return {"ok": True, "termux": self.status()["termux"]}
        if route == "device/termux/command/start":
            return self.start_termux()
        if route == "device/termux/command/stop":
            return self.stop_termux()
        return {"ok": False, "error": f"unknown android route: {route}", "uri": uri}


class UriNodeServer:
    def __init__(self, runtime: UriRuntime, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def send_json(self, code: int, data: dict[str, Any]) -> None:
                body = json.dumps(data, indent=2).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path.split("?", 1)[0] == "/health":
                    self.send_json(200, runtime.status())
                    return
                if self.path.split("?", 1)[0] == "/routes":
                    self.send_json(200, {"ok": True, "routes": ROUTES})
                    return
                self.send_json(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:
                if self.path.split("?", 1)[0] != "/run":
                    self.send_json(404, {"ok": False, "error": "not found"})
                    return
                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    req = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    self.send_json(400, {"ok": False, "error": "invalid JSON"})
                    return
                uri = str(req.get("uri") or "")
                if not uri:
                    self.send_json(400, {"ok": False, "error": "uri is required"})
                    return
                payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
                result = runtime.handle_uri(uri, payload)
                self.send_json(200 if result.get("ok") else 400, result)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        runtime.log("server-started", url=runtime.status()["url"])

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.thread = None


def _poll_service(port: int) -> dict[str, Any]:
    """Fetch /health from the background service (localhost).  Returns a status dict."""
    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {"ok": False, "url": f"http://{lan_ip()}:{port}", "termux": {"running": False}}


def _post_service(port: int, uri: str) -> dict[str, Any]:
    """POST a URI run command to the background service."""
    try:
        body = json.dumps({"uri": uri}).encode()
        url = f"http://127.0.0.1:{port}/run"
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json",
                                              "Connection": "close"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _start_android_service() -> None:
    """Start the HTTP-server foreground service declared in buildozer.spec.

    Uses PythonActivity.start_service() which sets all required Intent extras
    (serviceEntrypoint, pythonHome, androidPrivate, …) automatically so that
    PythonService.java can find and execute service/main.py.
    """
    try:
        from jnius import autoclass  # type: ignore[import]
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        PythonActivity.start_service(
            "urirun node",
            f"HTTP API running on port {DEFAULT_PORT}",
            "",
        )
    except Exception:
        pass  # on desktop or if service already running


def run_kivy_app() -> None:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.utils import platform

    on_android = platform == "android"

    # On Android: HTTP server lives in the foreground service (service/main.py).
    # On desktop: run the server inline so the app is self-contained for dev/testing.
    if on_android:
        _start_android_service()
        desktop_server = None
    else:
        runtime = UriRuntime(DEFAULT_PORT)
        desktop_server = UriNodeServer(runtime, port=DEFAULT_PORT)
        desktop_server.start()

    class NodeScreen(BoxLayout):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(orientation="vertical", padding=20, spacing=12, **kwargs)
            self.title_lbl = Label(text="urirun Android URI node", font_size="20sp",
                                   bold=True, size_hint_y=None, height=52)
            self.url_label = Label(text="Starting service…", font_size="14sp",
                                   size_hint_y=None, height=44)
            self.status_label = Label(text="", font_size="13sp", size_hint_y=None, height=44)
            self.start_btn = Button(text="Start Termux urirun node",
                                    size_hint_y=None, height=56, on_press=self.start_termux)
            self.stop_btn = Button(text="Stop Termux urirun node",
                                   size_hint_y=None, height=56, on_press=self.stop_termux)
            self.routes_label = Label(text="\n".join(r["uri"] for r in ROUTES),
                                      font_size="11sp", halign="left", valign="top")
            for item in (self.title_lbl, self.url_label, self.status_label,
                         self.start_btn, self.stop_btn, self.routes_label):
                self.add_widget(item)
            Clock.schedule_interval(self.refresh, 2.0)
            self.refresh(0)

        def _status(self) -> dict[str, Any]:
            if on_android:
                return _poll_service(DEFAULT_PORT)
            # Desktop: poll the inline server
            return _poll_service(DEFAULT_PORT)

        def start_termux(self, *_: Any) -> None:
            _post_service(DEFAULT_PORT, "android://device/termux/command/start")
            self.refresh(0)

        def stop_termux(self, *_: Any) -> None:
            _post_service(DEFAULT_PORT, "android://device/termux/command/stop")
            self.refresh(0)

        def refresh(self, _dt: float) -> None:
            status = self._status()
            running = status.get("ok", False)
            self.url_label.text = ("URI API: " + status.get("url", "—")) if running else "Service starting…"
            termux = status.get("termux", {})
            self.status_label.text = "Termux: " + ("running" if termux.get("running") else "stopped")

    class UrirunAndroidNodeApp(App):
        def build(self) -> NodeScreen:
            return NodeScreen()

        def on_stop(self) -> None:
            if desktop_server is not None:
                desktop_server.stop()

    UrirunAndroidNodeApp().run()


if __name__ == "__main__":
    run_kivy_app()
