from pathlib import Path
from urllib.request import Request, urlopen

MODELS = {
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def download(url: str, destination: Path) -> None:
    print(f"Downloading {destination.name}...")
    request = Request(url, headers={"User-Agent": "FacePhotoFinder/0.6"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    if destination.stat().st_size < 100_000:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded model appears invalid: {destination.name}")


def main() -> None:
    folder = Path(__file__).resolve().parents[1] / "models"
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        destination = folder / name
        if destination.exists() and destination.stat().st_size >= 100_000:
            print(f"Already installed: {name}")
            continue
        download(url, destination)
    print("Face models are ready.")


if __name__ == "__main__":
    main()
