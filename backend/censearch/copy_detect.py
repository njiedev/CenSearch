"""Perceptual hash ordering, SIFT/RANSAC alignment, then calibrated dense agreement."""

from dataclasses import dataclass
import cv2
import numpy as np

VERSION = "sift-dense-overlap-v2"


def phash(image):
    gray = cv2.cvtColor(cv2.resize(image, (32, 32)), cv2.COLOR_BGR2GRAY)
    low = cv2.dct(gray.astype(np.float32))[:8, :8].flatten()[1:]
    return low > np.median(low)


def hash_text(bits):
    return np.packbits(bits).tobytes().hex()


@dataclass
class Features:
    points: np.ndarray
    descriptors: np.ndarray | None
    shape: tuple
    hash: np.ndarray
    gray: np.ndarray


def features(image):
    scale = min(1.0, 1600 / max(image.shape[:2]))
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    keys, descriptors = cv2.SIFT_create(nfeatures=2500).detectAndCompute(gray, None)
    points = np.array([key.pt for key in keys], dtype=np.float32)
    return Features(points, descriptors, gray.shape, phash(image), gray)


def dense_agreement(original, candidate, matrix):
    height, width = original.shape
    scale = min(1.0, 256 / max(height, width))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    inverse = np.diag([scale, scale, 1.0]) @ np.linalg.inv(matrix)
    aligned = cv2.warpPerspective(candidate.gray, inverse, size)
    mask = cv2.warpPerspective(np.ones(candidate.shape, np.uint8), inverse, size, flags=cv2.INTER_NEAREST)
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
    source = cv2.resize(original.gray, size, interpolation=cv2.INTER_AREA)
    source = cv2.GaussianBlur(source.astype(np.float32), (0, 0), 1.5)
    aligned = cv2.GaussianBlur(aligned.astype(np.float32), (0, 0), 1.5)
    scores = []
    for y in range(0, size[1] - 23, 16):
        for x in range(0, size[0] - 23, 16):
            valid = mask[y : y + 24, x : x + 24] > 0
            if valid.mean() < 0.9:
                continue
            left = source[y : y + 24, x : x + 24][valid]
            right = aligned[y : y + 24, x : x + 24][valid]
            if left.std() < 6 or right.std() < 2:
                continue
            left = left - left.mean()
            right = right - right.mean()
            denominator = max(1e-6, np.linalg.norm(left) * np.linalg.norm(right))
            scores.append(float(left @ right / denominator))
    overlap = float(mask.mean())
    center = mask[int(size[1] * 0.3) : int(size[1] * 0.7), int(size[0] * 0.3) : int(size[0] * 0.7)]
    score = -1.0
    if len(scores) >= 6 and overlap >= 0.08:
        score = float(np.quantile(scores, 0.25))
    return {
        "dense_score": score,
        "dense_median": float(np.median(scores)) if scores else -1.0,
        "dense_tiles": len(scores),
        "overlap": overlap,
        "central_overlap": float(center.mean()) if center.size else 0.0,
    }


def geometry(original, candidate):
    empty = {
        "inliers": 0,
        "tentative": 0,
        "inlier_ratio": 0.0,
        "coverage": 0.0,
        "homography": None,
        "dense_score": -1.0,
    }
    if original.descriptors is None or candidate.descriptors is None:
        return empty
    if len(candidate.descriptors) < 2:
        return empty
    pairs = cv2.BFMatcher().knnMatch(original.descriptors, candidate.descriptors, k=2)
    good = []
    for pair in pairs:
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
            good.append(pair[0])
    # Keep the closest match per candidate keypoint.
    unique = {}
    for match in sorted(good, key=lambda item: -item.distance):
        unique[match.trainIdx] = match
    good = list(unique.values())
    if len(good) < 4:
        return empty | {"tentative": len(good)}
    source = original.points[[match.queryIdx for match in good]]
    target = candidate.points[[match.trainIdx for match in good]]
    cv2.setRNGSeed(20261009)
    matrix, mask = cv2.findHomography(source, target, cv2.RANSAC, 4.0)
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        return empty | {"tentative": len(good)}
    inliers = mask.ravel().astype(bool)
    count = int(inliers.sum())
    coverage = 0.0
    if count >= 3:
        coverage = float(cv2.contourArea(cv2.convexHull(source[inliers]))) / np.prod(original.shape)
    height, width = original.shape
    corners = cv2.perspectiveTransform(
        np.float32([[[0, 0], [width, 0], [width, height], [0, height]]]), matrix
    )[0]
    area = abs(cv2.contourArea(corners)) / np.prod(candidate.shape)
    plausible = (
        cv2.isContourConvex(corners) and 0.001 < area < 30 and coverage >= 0.015 and count / len(good) >= 0.35
    )
    result = {
        "inliers": count if plausible else 0,
        "raw_inliers": count,
        "tentative": len(good),
        "inlier_ratio": count / len(good),
        "coverage": float(coverage),
        "homography": matrix.tolist() if plausible else None,
        "dense_score": -1.0,
    }
    if plausible and count >= 6:
        try:
            result.update(dense_agreement(original, candidate, matrix))
        except np.linalg.LinAlgError:
            result["homography"] = None
            result["inliers"] = 0
    return result


def compare(original, candidate, mirrored):
    results = []
    for flipped, feature_set in ((False, candidate), (True, mirrored)):
        distance = int(np.count_nonzero(original.hash != feature_set.hash))
        result = geometry(original, feature_set)
        results.append(
            result
            | {
                "phash_distance": distance,
                "mirrored": flipped,
                "hash_stage": "near" if distance <= 12 else "crop_rescue",
            }
        )
    return max(results, key=lambda item: (item["dense_score"], item["inliers"], -item["phash_distance"]))


def verdict(evidence, calibration):
    if evidence["inliers"] < calibration["minimum_inliers"]:
        return "none"
    if (
        evidence.get("central_overlap", 0) >= 0.5
        and evidence["dense_score"] >= calibration["dense_threshold"]
    ):
        return "derived"
    if evidence["dense_score"] >= calibration["uncertain_threshold"]:
        return "uncertain"
    return "none"
