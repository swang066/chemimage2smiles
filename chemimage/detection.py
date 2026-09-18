"""Heuristic connected-region detection for clean, white-background schemes."""
import cv2
import numpy as np
from PIL import Image


def detect_regions(image: Image.Image) -> list[list[int]]:
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    # Dilate thin chemical bonds enough to connect each drawing, but keep
    # separate molecules apart. Text/arrows can still produce false positives.
    mask = (gray < 205).astype(np.uint8) * 255
    scale = max(1, round(min(width, height) / 900))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9 * scale, 9 * scale))
    joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(joined)
    boxes = []
    min_area = max(100, width * height * 0.00008)
    for x, y, w, h, area in stats[1:count]:
        if area < min_area or w < 16 or h < max(16, height * 0.065):
            continue
        if w > width * 0.9 or h > height * 0.9:
            continue
        # Long, thin reaction arrows are skipped.
        if w / h > 9 or h / w > 9:
            continue
        pad = 6 * scale
        boxes.append([max(0, int(x-pad)), max(0, int(y-pad)), min(width, int(x+w+pad)), min(height, int(y+h+pad))])
    return sorted(boxes, key=lambda b: (b[1] // max(1, height // 12), b[0], b[1]))


def validate_boxes(boxes: list, size: tuple[int, int]) -> list[list[int]]:
    width, height = size
    if len(boxes) > 200:
        raise ValueError("At most 200 regions are allowed")
    cleaned = []
    for box in boxes:
        if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
            raise ValueError("Each box must be four integer coordinates")
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Box is outside image bounds")
        cleaned.append(box)
    return cleaned