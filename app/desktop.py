import os
import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PREFERRED_PORT = 8765


def available_port(preferred: int = PREFERRED_PORT) -> int:
    for port in range(preferred, preferred + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port)); return port
            except OSError: continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0)); return int(sock.getsockname()[1])


def _open_when_ready(url: str) -> None:
    health=f"{url}/health"
    for _ in range(100):
        try:
            with urllib.request.urlopen(health,timeout=0.5) as response:
                if response.status==200:
                    if os.getenv("AUROARA_NO_BROWSER")!="1": webbrowser.open(url,new=1)
                    return
        except Exception: time.sleep(0.1)


def main() -> None:
    requested=os.getenv("AUROARA_DESKTOP_PORT")
    port=available_port(int(requested)) if requested else available_port()
    url=f"http://{HOST}:{port}"
    threading.Thread(target=_open_when_ready,args=(url,),daemon=True).start()
    uvicorn.run("app.main:app",host=HOST,port=port,log_level="info",access_log=False)


if __name__=="__main__": main()
