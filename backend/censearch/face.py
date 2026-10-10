"""YuNet/SFace with the prototype's calibrated native-tile and rotation pipeline."""

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from threading import RLock
import cv2
import numpy as np


@dataclass(frozen=True)
class FaceConfig:
    detector_score: float = 0.8
    min_size: int = 32
    min_blur: float = 15.0
    detector_long_side: int = 500
    tile_size: int = 640
    tile_stride: int = 448
    rotation_fallback: bool = True


@dataclass
class Face:
    box: list[float]
    embedding: np.ndarray
    detector_score: float
    blur: float


def active_references(references):
    """First 1/3/5 in upload order, rounded down; never choose a probe-specific subset."""
    if not len(references):
        raise ValueError("At least one reference is required")
    count = max(number for number in (1, 3, 5) if number <= len(references))
    return references[:count]


def band_for(score: float, calibration: dict) -> str:
    bands = calibration["deployment_bands"]
    if score >= bands["match"]["threshold"]:
        return "match"
    if score >= bands["possible"]["threshold"]:
        return "possible"
    return "no_match"


class OpenCVFaceEngine:
    def __init__(self, models_dir: Path, config: FaceConfig = FaceConfig()):
        self.config = config
        self.models_dir = models_dir
        self.lock = RLock()
        cv2.setNumThreads(1)
        self.detector = cv2.FaceDetectorYN_create(
            str(models_dir / "yunet.onnx"), "", (500, 500), config.detector_score, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF_create(str(models_dir / "sface.onnx"), "")

    def signature(self):
        weights = {}
        for name in ("yunet", "sface"):
            with (self.models_dir / f"{name}.onnx").open("rb") as stream:
                weights[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        return {
            "opencv": cv2.__version__,
            "engine": "YuNet-2023mar/SFace-2021dec/native-tiles-rotation-v4",
            "quality": asdict(self.config),
            "weights": weights,
        }

    def detect_rows(self, image, overview_only=False):
        height, width = image.shape[:2]
        views = [(image, 0, 0, self.config.detector_long_side / max(height, width))]
        tile = self.config.tile_size
        if max(height, width) > tile and not overview_only:

            def starts(length):
                positions = range(0, max(1, length - tile + 1), self.config.tile_stride)
                return sorted(set([*positions, max(0, length - tile)]))

            for y in starts(height):
                for x in starts(width):
                    views.append((image[y : y + tile, x : x + tile], x, y, 1.0))
        proposals = []
        for view, x, y, scale in views:
            resized = cv2.resize(view, None, fx=scale, fy=scale) if scale != 1 else view
            self.detector.setInputSize((resized.shape[1], resized.shape[0]))
            _, rows = self.detector.detect(resized)
            if rows is None:
                continue
            for detected in rows:
                row = detected.copy()
                row[:14] /= scale
                row[0] += x
                row[1] += y
                row[4:14:2] += x
                row[5:14:2] += y
                proposals.append((scale, row))
        kept = []
        for _, row in sorted(proposals, key=lambda item: (item[0], item[1][14]), reverse=True):
            x, y, width, height = row[:4]
            duplicate = False
            for other in kept:
                ox, oy, ow, oh = other[:4]
                overlap = max(0, min(x + width, ox + ow) - max(x, ox))
                overlap *= max(0, min(y + height, oy + oh) - max(y, oy))
                if overlap / max(1, min(width * height, ow * oh)) > 0.5:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(row)
        return kept

    def upright(self, image):
        height, width = image.shape[:2]
        rows = self.detect_rows(image)
        if not rows:
            return [], ["no_detection"]
        found = []
        skipped = []
        for row in rows:
            x, y, face_width, face_height = row[:4]
            if min(face_width, face_height) < self.config.min_size:
                skipped.append("face_too_small")
                continue
            crop = image[
                max(0, int(y)) : min(height, int(y + face_height)),
                max(0, int(x)) : min(width, int(x + face_width)),
            ]
            if not crop.size:
                skipped.append("empty_crop")
                continue
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur < self.config.min_blur:
                skipped.append("blur")
                continue
            aligned = self.recognizer.alignCrop(image, row)
            embedding = self.recognizer.feature(aligned).flatten().astype(np.float32)
            embedding /= np.linalg.norm(embedding)
            found.append(Face(row[:4].tolist(), embedding, float(row[14]), blur))
        return found, skipped

    def extract(self, image):
        # OpenCV detectors mutate their input size and are not thread-safe.
        with self.lock:
            return self._extract(image)

    def _extract(self, image):
        found, skipped = self.upright(image)
        if not self.config.rotation_fallback:
            return found, skipped
        height, width = image.shape[:2]
        alternatives = [(found, skipped)] if found else []
        upright_found = bool(found)
        best_confidence = max((face.detector_score for face in found), default=0.0)
        for turns in (1, 2, 3):
            rotated = np.ascontiguousarray(np.rot90(image, turns))
            if upright_found:
                rows = self.detect_rows(rotated, overview_only=True)
                if not rows or max(row[14] for row in rows) <= best_confidence:
                    continue
            faces, rotation_skips = self.upright(rotated)
            if not faces:
                continue
            for face in faces:
                x, y, face_width, face_height = face.box
                if turns == 1:
                    face.box = [width - y - face_height, x, face_height, face_width]
                elif turns == 2:
                    face.box = [width - x - face_width, height - y - face_height, face_width, face_height]
                else:
                    face.box = [y, height - x - face_width, face_height, face_width]
            alternatives.append((faces, rotation_skips))
            best_confidence = max(best_confidence, max(face.detector_score for face in faces))
        if alternatives:
            return max(alternatives, key=lambda result: max(face.detector_score for face in result[0]))
        return [], skipped
