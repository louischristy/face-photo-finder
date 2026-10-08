import json
import os
import platform
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 18765


def executable_path() -> Path:
    if platform.system() == "Darwin":
        return ROOT / "dist" / "Auroara Face Photo Finder.app" / "Contents" / "MacOS" / "Auroara Face Photo Finder"
    suffix = ".exe" if platform.system() == "Windows" else ""
    return ROOT / "dist" / "Auroara Face Photo Finder" / f"Auroara Face Photo Finder{suffix}"


def main() -> None:
    executable = executable_path()
    if not executable.exists():
        raise SystemExit(f"Packaged executable not found: {executable}")
    with tempfile.TemporaryDirectory(prefix="auroara-fpf-smoke-") as temp_dir:
        env = os.environ.copy()
        env["AUROARA_DATA_DIR"] = temp_dir
        env["AUROARA_DESKTOP_PORT"] = str(PORT)
        env["AUROARA_NO_BROWSER"] = "1"
        process = subprocess.Popen([str(executable)], env=env)
        try:
            url = f"http://{HOST}:{PORT}/health"
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError(f"Packaged application exited with {process.returncode}")
                try:
                    with urllib.request.urlopen(url, timeout=0.5) as response:
                        if response.status == 200:
                            payload = json.load(response)
                            licence = payload.get("licence", {})
                            if licence.get("active") is not False:
                                raise RuntimeError("Fresh packaged app unexpectedly bypassed product activation")
                            print(f"Packaged application healthy and activation-gated: {url}")
                            return
                except RuntimeError:
                    raise
                except Exception:
                    time.sleep(0.25)
            raise RuntimeError("Packaged application did not become healthy")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
