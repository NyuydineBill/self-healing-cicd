import html
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config.settings import get_settings
from utils.approval import format_patch_diff
from utils.logging import get_logger

logger = get_logger("approval_web")

_PENDING_FILE = "pending_approval.json"


class _ApprovalState:
    def __init__(self) -> None:
        self.decision: bool | None = None
        self.pending: dict = {}


def _pending_path() -> Path:
    return get_settings().results_dir / _PENDING_FILE


def _approval_page(pending: dict) -> str:
    diff = html.escape(pending.get("diff", ""))
    target = html.escape(pending.get("target_file", ""))
    run_id = html.escape(str(pending.get("run_id", "")))
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Self-Healing Patch Approval</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; }}
    pre {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; overflow: auto; }}
    .actions a {{
      display: inline-block; margin-right: 1rem; padding: 0.6rem 1.2rem;
      text-decoration: none; border-radius: 6px; font-weight: 600;
    }}
    .approve {{ background: #238636; color: #fff; }}
    .reject {{ background: #da3633; color: #fff; }}
    h1 {{ font-size: 1.4rem; }}
  </style>
</head>
<body>
  <h1>Patch approval required</h1>
  <p><strong>File:</strong> {target}</p>
  <p><strong>Run:</strong> {run_id}</p>
  <pre>{diff}</pre>
  <div class="actions">
    <a class="approve" href="/approve">Approve patch</a>
    <a class="reject" href="/reject">Reject patch</a>
  </div>
</body>
</html>"""


def _done_page(approved: bool) -> str:
    msg = "Patch approved. You can close this tab." if approved else "Patch rejected."
    color = "#238636" if approved else "#da3633"
    return f"""<!DOCTYPE html>
<html><body style="font-family:system-ui;margin:2rem">
<h2 style="color:{color}">{html.escape(msg)}</h2>
</body></html>"""


class ApprovalWebServer:
    """Minimal local web UI for patch approval."""

    def __init__(self, port: int | None = None):
        settings = get_settings()
        self.port = port or settings.web_approval_port
        self.timeout = settings.web_approval_timeout
        self._state = _ApprovalState()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _make_handler(self) -> type:
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                logger.debug("approval_web: " + fmt, *args)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path in ("/approve", "/reject"):
                    state.decision = parsed.path == "/approve"
                    body = _done_page(state.decision).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                body = _approval_page(state.pending).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._server = HTTPServer(("127.0.0.1", self.port), self._make_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Approval web UI at http://127.0.0.1:%d", self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def wait_for_decision(
        self,
        *,
        target_file: str,
        original_content: str,
        patch_content: str,
        run_id: str | int = "",
    ) -> bool:
        diff = format_patch_diff(target_file, original_content, patch_content)
        pending = {
            "target_file": target_file,
            "run_id": run_id,
            "diff": diff,
            "status": "pending",
        }
        self._state.pending = pending
        self._state.decision = None

        path = _pending_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pending, indent=2), encoding="utf-8")

        self.start_background()
        if get_settings().web_approval_open_browser:
            webbrowser.open(f"http://127.0.0.1:{self.port}/")

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self._state.decision is not None:
                approved = self._state.decision
                pending["status"] = "approved" if approved else "rejected"
                path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
                self.stop()
                return approved
            time.sleep(0.3)

        pending["status"] = "timeout"
        path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
        self.stop()
        logger.warning("Web approval timed out after %ds", self.timeout)
        return False


def run_standalone_server(port: int | None = None) -> None:
    """Run approval UI server until Ctrl+C (for manual testing)."""
    server = ApprovalWebServer(port=port)
    server._state.pending = {
        "target_file": "(waiting)",
        "run_id": "",
        "diff": "No pending patch. Run main.py with WEB_APPROVAL_ENABLED=true.",
        "status": "idle",
    }
    server._server = HTTPServer(("127.0.0.1", server.port), server._make_handler())
    logger.info("Standalone approval UI: http://127.0.0.1:%d (Ctrl+C to stop)", server.port)
    try:
        server._server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Approval server stopped")
