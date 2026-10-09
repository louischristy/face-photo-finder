from pathlib import Path
from urllib.request import Request, urlopen

MODELS = {
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def download(url: str, target: Path) -> None:
    print(f"Downloading {target.name}...")
    request = Request(url, headers={"User-Agent": "Face-Photo-Finder/0.6"})
    with urlopen(request, timeout=120) as response, target.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
    if target.stat().st_size < 100_000:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded model looks invalid: {target.name}")


def main() -> None:
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    for filename, url in MODELS.items():
        target = model_dir / filename
        if target.exists() and target.stat().st_size >= 100_000:
            print(f"OK: {filename}")
            continue
        download(url, target)
        print(f"Installed: {filename} ({target.stat().st_size:,} bytes)")
    print("Face models are ready.")


if __name__ == "__main__":
    main()
