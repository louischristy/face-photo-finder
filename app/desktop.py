import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

# PyInstaller's Windows windowed bootloader deliberately sets stdout/stderr to
# None. Uvicorn's logging setup expects file-like streams, so provide harmless
# sinks before importing/configuring Uvicorn. This keeps the release executable
# console-free without leaving startup failures behind a Windows error dialog.
_devnull_streams = []
for stream_name in ("stdout", "stderr"):
    if getattr(sys, stream_name) is None:
        stream = open(os.devnull, "w", encoding="utf-8")
        _devnull_streams.append(stream)
        setattr(sys, stream_name, stream)

import uvicorn

# Import the application directly so PyInstaller can discover and bundle the
# complete app package. A string import works from source but is invisible to
# PyInstaller's static dependency analysis.
from app.main import app

HOST = "127.0.0.1"
PREFERRED_PORT = 8765


def available_port(preferred: int = PREFERRED_PORT) -> int:
    for port in range(preferred, preferred + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def _open_when_ready(url: str) -> None:
    health = f"{url}/health"
    for _ in range(100):
        try:
            with urllib.request.urlopen(health, timeout=0.5) as response:
                if response.status == 200:
                    if os.getenv("AUROARA_NO_BROWSER") != "1":
                        webbrowser.open(url, new=1)
                    return
        except Exception:
            time.sleep(0.1)


def main() -> None:
    requested = os.getenv("AUROARA_DESKTOP_PORT")
    port = available_port(int(requested)) if requested else available_port()
    url = f"http://{HOST}:{port}"
    threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
