import argparse
import json
import os
import platform
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"


def executable_path() -> Path:
    if platform.system() == "Darwin":
        return ROOT / "dist" / "Auroara Face Photo Finder.app" / "Contents" / "MacOS" / "Auroara Face Photo Finder"
    suffix = ".exe" if platform.system() == "Windows" else ""
    return ROOT / "dist" / "Auroara Face Photo Finder" / f"Auroara Face Photo Finder{suffix}"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def get(url: str):
    return urllib.request.urlopen(url, timeout=1)


def smoke(executable: Path) -> None:
    executable = executable.resolve()
    if not executable.exists():
        raise SystemExit(f"Packaged executable not found: {executable}")
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="auroara-fpf-smoke-") as temp_dir:
        env = os.environ.copy()
        env["AUROARA_DATA_DIR"] = temp_dir
        env["AUROARA_DESKTOP_PORT"] = str(port)
        env["AUROARA_NO_BROWSER"] = "1"
        process = subprocess.Popen([str(executable)], env=env)
        try:
            base_url = f"http://{HOST}:{port}"
            health_url = f"{base_url}/health"
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError(f"Packaged application exited with {process.returncode}")
                try:
                    with get(health_url) as response:
                        if response.status != 200:
                            continue
                        payload = json.load(response)
                        licence = payload.get("licence", {})
                        if licence.get("active") is not False:
                            raise RuntimeError("Fresh packaged app unexpectedly bypassed product activation")
                        if payload.get("status") != "setup_required":
                            raise RuntimeError(f"Unexpected fresh-install health state: {payload.get('status')!r}")

                    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                    with opener.open(base_url + "/", timeout=1) as response:
                        if response.geturl().rstrip("/") != (base_url + "/activate").rstrip("/"):
                            raise RuntimeError(f"Fresh packaged app did not route to activation: {response.geturl()}")
                        activation_html = response.read().decode("utf-8", errors="replace")
                        if "activat" not in activation_html.lower():
                            raise RuntimeError("Activation page did not render expected activation content")

                    print(f"Application healthy, activation-gated, and first-run route verified: {executable}")
                    return
                except RuntimeError:
                    raise
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    time.sleep(0.25)
            raise RuntimeError("Packaged application did not become healthy")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a packaged or installed Auroara Face Photo Finder executable")
    parser.add_argument("--executable", type=Path, help="Path to an installed/package executable; defaults to the build output")
    args = parser.parse_args()
    smoke(args.executable or executable_path())


if __name__ == "__main__":
    main()
