"""Install only YuNet/SFace; no dataset downloads. Verify before atomic replacement."""

import argparse
import hashlib
from pathlib import Path
import shutil
import httpx

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "yunet": (
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "sface": (
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def setup(source=None, destination=ROOT / "models"):
    destination.mkdir(parents=True, exist_ok=True)
    for name, (remote, expected) in ASSETS.items():
        target = destination / f"{name}.onnx"
        if target.exists() and digest(target) == expected:
            print(f"SHA256 verified {target.name}")
            continue
        temporary = target.with_suffix(".part")
        try:
            candidate = source / target.name if source else None
            if candidate and candidate.is_file() and digest(candidate) == expected:
                shutil.copyfile(candidate, temporary)
                method = "copied verified local weights"
            else:
                url = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/" + remote
                with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_bytes():
                            stream.write(chunk)
                method = "downloaded OpenCV Zoo weights"
            if digest(temporary) != expected:
                raise ValueError(f"Checksum mismatch: {name}")
            temporary.replace(target)
            print(f"SHA256 verified {target.name}: {method}")
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    setup(args.source, args.destination)
