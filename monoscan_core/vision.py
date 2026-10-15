"""N2: real-image local features and uniquely indexed cross-checked matches."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class VisionError(ValueError):
    pass


@dataclass
class FrameFeatures:
    name: str
    image: np.ndarray
    k: np.ndarray
    points: np.ndarray
    descriptors: np.ndarray


def read_image(path: Path, *, max_side: int = 1600):
    # Keep unrotated buffer coordinates: the capture contract stores K for these pixels.
    flag = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION
    img = cv2.imread(str(path), flag)
    if img is None or img.ndim != 3 or min(img.shape[:2]) < 32:
        raise VisionError(f"Cannot decode a valid image: {path.name}")
    height, width = img.shape[:2]
    scale = min(1.0, max_side / max(width, height))
    if scale != 1:
        img = cv2.resize(img, (round(width * scale), round(height * scale)),
                         interpolation=cv2.INTER_AREA)
    return img, (width, height)


def extract(name: str, image: np.ndarray, k: np.ndarray, max_features=4000):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if np.std(gray) < 5:
        raise VisionError(f"Insufficient image texture: {name}")
    sift = cv2.SIFT_create(nfeatures=max_features)
    keypoints, descriptors = sift.detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 24:
        raise VisionError(f"Insufficient features: {name}")
    pts = np.asarray([key.pt for key in keypoints], dtype=np.float64)
    return FrameFeatures(name, image, k, pts, descriptors)


def match(a: FrameFeatures, b: FrameFeatures, ratio=0.76):
    """Unique (a_keypoint, b_keypoint) pairs with reciprocal Lowe ratio checks."""
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    ab = matcher.knnMatch(a.descriptors, b.descriptors, k=2)
    ba = matcher.knnMatch(b.descriptors, a.descriptors, k=2)
    def accepted(knn):
        return {m.queryIdx: m.trainIdx for pair in knn if len(pair) == 2
                for m, n in [pair] if m.distance < ratio * n.distance}
    forward, backward = accepted(ab), accepted(ba)
    return np.asarray(sorted((i, j) for i, j in forward.items()
                             if backward.get(j) == i), dtype=np.int32).reshape(-1, 2)
