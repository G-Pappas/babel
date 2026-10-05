"""Which monitors actually show the wallpaper, straight from Hyprland's IPC sockets.

A monitor counts as watched when its display is on, no special workspace is
open over it, and its active workspace has no windows at all.
"""

import json
import os
import socket
from pathlib import Path


class Hyprland:
    def __init__(self):
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        runtime = os.environ.get("XDG_RUNTIME_DIR")  # never a shared /tmp fallback
        base = Path(runtime) / "hypr" / sig if sig and runtime else None
        self.request_path = base / ".socket.sock" if base else None
        self.event_path = base / ".socket2.sock" if base else None
        self.available = bool(self.request_path and self.request_path.exists())
        self.events = None

    def request(self, what):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(self.request_path))
            s.sendall(f"j/{what}".encode())
            chunks = []
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)
        return json.loads(b"".join(chunks) or b"null")

    def clear_monitors(self):
        """{monitor name: True if nothing covers the wallpaper there}."""
        if not self.available:
            return {}
        try:
            monitors = self.request("monitors")
            clients = self.request("clients")
        except (OSError, ValueError):
            return {}
        busy = {c["workspace"]["id"] for c in clients if c.get("mapped", True) and not c.get("hidden", False)}
        return {m["name"]: (m.get("dpmsStatus", True) and not m.get("disabled", False)
                            and m.get("specialWorkspace", {}).get("id", 0) == 0
                            and m["activeWorkspace"]["id"] not in busy)
                for m in monitors}

    def open_events(self):
        """A socket that becomes readable whenever windows or workspaces change."""
        if not (self.event_path and self.event_path.exists()):
            return None
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(str(self.event_path))
        s.setblocking(False)
        self.events = s
        return s

    def drain(self):
        try:
            while self.events.recv(65536):
                pass
        except (BlockingIOError, OSError):
            pass
