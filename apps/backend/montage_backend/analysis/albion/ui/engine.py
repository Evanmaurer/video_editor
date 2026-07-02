from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiElementType
from montage_backend.analysis.albion.ui.templates import AlbionUiRegionTemplate, AlbionUiTemplate, region_to_pixels


@dataclass(frozen=True)
class RawUiDetection:
    element_type: AlbionUiElementType
    label: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    region_name: str


class AlbionUiDetectionEngine:
    """Template-guided OpenCV heuristics for Albion HUD elements."""

    engine_id = "template_heuristic"
    version = "1.0"

    def is_available(self) -> bool:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401

            return True
        except ImportError:
            return False

    def detect_png(
        self,
        png_bytes: bytes,
        *,
        template: AlbionUiTemplate,
    ) -> list[RawUiDetection]:
        if not png_bytes or not self.is_available():
            return []

        import cv2
        import numpy as np

        array = np.frombuffer(png_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        height, width = image.shape[:2]
        detections: list[RawUiDetection] = []
        for region_name, region in template.regions.items():
            detections.extend(
                self._detect_region(
                    image,
                    width,
                    height,
                    region_name=region_name,
                    region=region,
                ),
            )
        return detections

    def _detect_region(
        self,
        image,
        width: int,
        height: int,
        *,
        region_name: str,
        region: AlbionUiRegionTemplate,
    ) -> list[RawUiDetection]:
        x, y, w, h = region_to_pixels(region, frame_width=width, frame_height=height)
        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return []

        strategy = region.detector
        if strategy == "auto":
            strategy = _default_strategy(region.element_type)

        if strategy == "edge_density":
            return self._detect_edge_density(region, region_name, x, y, w, h, roi)
        if strategy == "stack_contours":
            return self._detect_stack_contours(region, region_name, x, y, w, h, roi)
        if strategy == "color_bars":
            return self._detect_color_bars(region, region_name, image, x, y, w, h)
        if strategy == "panel_edges":
            return self._detect_panel_edges(region, region_name, image, width, height, x, y, w, h)
        if strategy == "bright_effects":
            return self._detect_bright_effects(region, region_name, x, y, w, h, roi)
        return []

    def _detect_edge_density(
        self,
        region: AlbionUiRegionTemplate,
        region_name: str,
        x: int,
        y: int,
        w: int,
        h: int,
        roi,
    ) -> list[RawUiDetection]:
        import cv2

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 140)
        edge_ratio = float(edges.mean()) / 255.0
        min_ratio = 0.03 if region.element_type == AlbionUiElementType.MINIMAP else 0.025
        if edge_ratio < min_ratio:
            return []
        confidence = round(min(0.88, 0.42 + edge_ratio * 2.5), 3)
        return [
            RawUiDetection(
                element_type=region.element_type,
                label=region_name,
                confidence=confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                region_name=region_name,
            ),
        ]

    def _detect_stack_contours(
        self,
        region: AlbionUiRegionTemplate,
        region_name: str,
        x: int,
        y: int,
        w: int,
        h: int,
        roi,
    ) -> list[RawUiDetection]:
        import cv2

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_like = 0
        for contour in contours:
            _, _, cw, ch = cv2.boundingRect(contour)
            if 20 <= cw <= w and 12 <= ch <= int(h * 0.18):
                frame_like += 1
        if frame_like < 2:
            return []
        confidence = round(min(0.82, 0.35 + frame_like * 0.08), 3)
        return [
            RawUiDetection(
                element_type=region.element_type,
                label=region_name,
                confidence=confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                region_name=region_name,
            ),
        ]

    def _detect_color_bars(
        self,
        region: AlbionUiRegionTemplate,
        region_name: str,
        image,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> list[RawUiDetection]:
        import cv2
        import numpy as np

        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return []

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 80, 80])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 80, 80])
        upper_red2 = np.array([180, 255, 255])
        lower_green = np.array([35, 60, 60])
        upper_green = np.array([90, 255, 255])
        mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        mask |= cv2.inRange(hsv, lower_green, upper_green)
        ratio = float(mask.mean()) / 255.0
        if ratio < 0.02:
            return []
        confidence = round(min(0.8, 0.45 + ratio * 3.0), 3)
        return [
            RawUiDetection(
                element_type=region.element_type,
                label=region_name,
                confidence=confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                region_name=region_name,
            ),
        ]

    def _detect_panel_edges(
        self,
        region: AlbionUiRegionTemplate,
        region_name: str,
        image,
        width: int,
        height: int,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> list[RawUiDetection]:
        import cv2

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120)
        roi_edges = edges[y : y + h, x : x + w]
        edge_ratio = float(roi_edges.mean()) / 255.0
        if edge_ratio < 0.03:
            return []
        touches_edge = x <= 4 or y <= 4 or x + w >= width - 4 or y + h >= height - 4
        if not touches_edge:
            return []
        confidence = round(min(0.75, 0.4 + edge_ratio * 2.0), 3)
        return [
            RawUiDetection(
                element_type=region.element_type,
                label=region_name,
                confidence=confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                region_name=region_name,
            ),
        ]

    def _detect_bright_effects(
        self,
        region: AlbionUiRegionTemplate,
        region_name: str,
        x: int,
        y: int,
        w: int,
        h: int,
        roi,
    ) -> list[RawUiDetection]:
        import cv2

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        bright_sat = ((saturation > 120) & (value > 180)).astype("uint8") * 255
        ratio = float(bright_sat.mean()) / 255.0
        if ratio < 0.02:
            return []
        confidence = round(min(0.78, 0.4 + ratio * 4.0), 3)
        return [
            RawUiDetection(
                element_type=region.element_type,
                label=region_name,
                confidence=confidence,
                x=x,
                y=y,
                width=w,
                height=h,
                region_name=region_name,
            ),
        ]


class UnavailableUiDetectionEngine(AlbionUiDetectionEngine):
    engine_id = "unavailable"
    version = "0.0.0"

    def is_available(self) -> bool:
        return True

    def detect_png(self, png_bytes: bytes, *, template: AlbionUiTemplate) -> list[RawUiDetection]:
        _ = png_bytes, template
        return []


def resolve_ui_detection_engine() -> AlbionUiDetectionEngine:
    engine = AlbionUiDetectionEngine()
    if engine.is_available():
        return engine
    return UnavailableUiDetectionEngine()


def _default_strategy(element_type: AlbionUiElementType) -> str:
    mapping = {
        AlbionUiElementType.PARTY_FRAME: "stack_contours",
        AlbionUiElementType.MINIMAP: "edge_density",
        AlbionUiElementType.HEALTH_BAR: "color_bars",
        AlbionUiElementType.ABILITY_BAR: "edge_density",
        AlbionUiElementType.KILL_FEED: "edge_density",
        AlbionUiElementType.UI_PANEL: "panel_edges",
        AlbionUiElementType.SPELL_EFFECT: "bright_effects",
        AlbionUiElementType.CHAT_PANEL: "panel_edges",
        AlbionUiElementType.RESOURCE_BAR: "color_bars",
    }
    return mapping.get(element_type, "edge_density")
