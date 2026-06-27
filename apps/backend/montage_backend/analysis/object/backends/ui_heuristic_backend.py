from __future__ import annotations

from montage_backend.analysis.object.engine import ObjectDetector, RawObjectDetection


class UiHeuristicObjectDetector(ObjectDetector):
    """OpenCV heuristics for game HUD elements until custom Albion models ship."""

    detector_id = "ui_heuristic"
    version = "1.0"

    def is_available(self) -> bool:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401

            return True
        except ImportError:
            return False

    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        if not png_bytes:
            return []

        import cv2
        import numpy as np

        array = np.frombuffer(png_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        height, width = image.shape[:2]
        detections: list[RawObjectDetection] = []
        detections.extend(self._detect_minimap(image, width, height))
        detections.extend(self._detect_party_frames(image, width, height))
        detections.extend(self._detect_health_bars(image, width, height))
        detections.extend(self._detect_ui_panels(image, width, height))
        detections.extend(self._detect_spell_effects(image, width, height))
        return detections

    def _detect_minimap(self, image, width: int, height: int) -> list[RawObjectDetection]:
        import cv2

        x = int(width * 0.78)
        y = int(height * 0.72)
        w = max(width - x, 1)
        h = max(height - y, 1)
        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return []

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 140)
        edge_ratio = float(edges.mean()) / 255.0
        if edge_ratio < 0.04:
            return []

        return [
            RawObjectDetection(
                category="minimap",
                label="minimap_region",
                confidence=round(min(0.85, 0.45 + edge_ratio), 3),
                x=x,
                y=y,
                width=w,
                height=h,
                source_model=self.detector_id,
            ),
        ]

    def _detect_party_frames(self, image, width: int, height: int) -> list[RawObjectDetection]:
        import cv2

        x = 0
        y = int(height * 0.12)
        w = int(width * 0.16)
        h = int(height * 0.55)
        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return []

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_like = 0
        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if 20 <= cw <= w and 12 <= ch <= int(h * 0.18):
                frame_like += 1
        if frame_like < 2:
            return []

        return [
            RawObjectDetection(
                category="party_frame",
                label="party_frame_stack",
                confidence=round(min(0.8, 0.35 + frame_like * 0.08), 3),
                x=x,
                y=y,
                width=w,
                height=h,
                source_model=self.detector_id,
            ),
        ]

    def _detect_health_bars(self, image, width: int, height: int) -> list[RawObjectDetection]:
        import cv2
        import numpy as np

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 80, 80])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 80, 80])
        upper_red2 = np.array([180, 255, 255])
        lower_green = np.array([35, 60, 60])
        upper_green = np.array([90, 255, 255])
        mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        mask |= cv2.inRange(hsv, lower_green, upper_green)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[RawObjectDetection] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 40 or h < 4 or h > 20 or w / max(h, 1) < 4:
                continue
            detections.append(
                RawObjectDetection(
                    category="health_bar",
                    label="health_bar",
                    confidence=0.62,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    source_model=self.detector_id,
                ),
            )
        return detections[:8]

    def _detect_ui_panels(self, image, width: int, height: int) -> list[RawObjectDetection]:
        import cv2

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[RawObjectDetection] = []
        frame_area = width * height
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_area * 0.08 or area > frame_area * 0.45:
                continue
            touches_edge = x <= 4 or y <= 4 or x + w >= width - 4 or y + h >= height - 4
            if not touches_edge:
                continue
            detections.append(
                RawObjectDetection(
                    category="ui_panel",
                    label="ui_panel",
                    confidence=0.58,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    source_model=self.detector_id,
                ),
            )
        return detections[:4]

    def _detect_spell_effects(self, image, width: int, height: int) -> list[RawObjectDetection]:
        import cv2
        import numpy as np

        x = int(width * 0.15)
        y = int(height * 0.15)
        w = int(width * 0.7)
        h = int(height * 0.7)
        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return []

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        bright_sat = ((saturation > 120) & (value > 180)).astype("uint8") * 255
        ratio = float(bright_sat.mean()) / 255.0
        if ratio < 0.02:
            return []

        return [
            RawObjectDetection(
                category="spell_effect",
                label="bright_effect",
                confidence=round(min(0.75, 0.4 + ratio * 4.0), 3),
                x=x,
                y=y,
                width=w,
                height=h,
                source_model=self.detector_id,
            ),
        ]
