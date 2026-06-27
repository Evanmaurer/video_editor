from __future__ import annotations

from montage_backend.analysis.object.engine import ObjectDetector, RawObjectDetection

_model = None

YOLO_COCO_CATEGORY_MAP: dict[int, tuple[str, str]] = {
    0: ("character", "person"),
    17: ("mount", "horse"),
}


class YoloObjectDetector(ObjectDetector):
    detector_id = "yolov8"
    version = "8.0"

    def __init__(self, *, gpu: bool = False, model_name: str = "yolov8n.pt") -> None:
        self._gpu = gpu
        self._model_name = model_name

    def is_available(self) -> bool:
        try:
            import ultralytics  # noqa: F401

            return True
        except ImportError:
            return False

    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        if not png_bytes:
            return []

        import cv2
        import numpy as np

        model = self._get_model()
        array = np.frombuffer(png_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        results = model.predict(image, verbose=False)
        detections: list[RawObjectDetection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls.item())
                mapping = YOLO_COCO_CATEGORY_MAP.get(class_id)
                if mapping is None:
                    continue
                category, label = mapping
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                width = max(x2 - x1, 1)
                height = max(y2 - y1, 1)
                detections.append(
                    RawObjectDetection(
                        category=category,
                        label=label,
                        confidence=confidence,
                        x=x1,
                        y=y1,
                        width=width,
                        height=height,
                        source_model=self.detector_id,
                    ),
                )
        return detections

    def _get_model(self):
        global _model
        if _model is None:
            from ultralytics import YOLO

            _model = YOLO(self._model_name)
        return _model
