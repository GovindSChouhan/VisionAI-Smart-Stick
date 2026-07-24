"""
Purpose: Capture Pi Camera frames, detect people/chairs, and prepare MJPEG.
Interview Explanation: "A dedicated vision thread captures frames, runs a
  pretrained MobileNet SSD model, and shares the latest annotated JPEG with
  both the alert engine and web dashboard."
Key Concepts: Picamera2, OpenCV DNN inference, Caffe model files, thread-safe
  shared state, JPEG encoding, MJPEG streaming.
Important Things to Remember: This is object detection, not stair detection.
  The model files are not included and must be placed in models/.
Dependencies: picamera2, OpenCV (cv2), NumPy, Python standard library.
Why This File Exists: Camera ownership, ML inference, and JPEG generation must
  stay together so multiple browser requests never compete for the Pi Camera.
Depends On: Picamera2, cv2, numpy, and both Caffe model files in models/.
Depended On By: main.py starts/stops it; alerts.py reads flags; web.py streams JPEGs.

Source notes: Picamera2 configuration/capture follows the Raspberry Pi
Picamera2 manual. cv2.dnn.readNetFromCaffe and cv2.dnn.blobFromImage follow
the official OpenCV DNN API. The worker-thread/cached-frame design is a common
producer-consumer pattern; it is not copied from a specific tutorial.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np
from picamera2 import Picamera2

LOGGER = logging.getLogger(__name__)

# These indexes are defined by the MobileNet SSD model trained on PASCAL VOC.
CLASS_NAMES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
    "car", "cat", "chair", "cow", "diningtable", "dog", "horse",
    "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor",
]
INTERESTING_CLASSES = {"person", "chair"}


@dataclass(frozen=True)
class VisionSnapshot:
    """Latest object flags exposed to alerts and the /sensors endpoint."""

    person: bool = False
    chair: bool = False


class VisionSystem:
    """Own the camera and continuously produce one latest annotated JPEG frame."""

    def __init__(self, model_dir: Path, confidence_threshold: float = 0.50) -> None:
        """Create the camera/AI service, but do not access hardware yet.

        Parameters: model_dir contains the Caffe .prototxt and .caffemodel;
        confidence_threshold filters weak predictions. Return: none.
        Why: separating construction from start makes errors happen at a clear
        startup stage. Interview explanation: "The model threshold reduces
        false positives before an object can generate a voice warning."
        """
        self._model_dir = model_dir
        self._confidence_threshold = confidence_threshold
        self._camera: Optional[Picamera2] = None
        self._network: Optional[cv2.dnn.Net] = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._latest_jpeg: Optional[bytes] = None
        self._latest_snapshot = VisionSnapshot()

    def start(self) -> None:
        """Load the model, start the Pi camera, then start the capture thread.

        Parameters/return: none. Edge case: missing model files raise a clear
        FileNotFoundError before Flask starts. Interview explanation: "Camera
        work is isolated in one worker so it never blocks the web server."
        """
        prototxt = self._model_dir / "MobileNetSSD_deploy.prototxt"
        weights = self._model_dir / "MobileNetSSD_deploy.caffemodel"
        if not prototxt.is_file() or not weights.is_file():
            raise FileNotFoundError(
                "Put MobileNetSSD_deploy.prototxt and "
                "MobileNetSSD_deploy.caffemodel in models/."
            )

        self._network = cv2.dnn.readNetFromCaffe(str(prototxt), str(weights))
        self._camera = Picamera2()
        configuration = self._camera.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self._camera.configure(configuration)
        self._camera.start()
        self._running.set()
        self._thread = threading.Thread(
            target=self._capture_loop, name="vision-loop", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker and release the camera.

        Parameters/return: none. The join has a timeout so shutdown cannot
        hang forever. Interview explanation: "I release hardware cleanly."
        """
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._camera is not None:
            self._camera.stop()

    def latest_snapshot(self) -> VisionSnapshot:
        """Return the latest immutable detection flags without exposing locks.

        Return: VisionSnapshot. Important logic: the lock prevents Flask and
        the alert thread from reading state while the camera thread replaces it.
        """
        with self._lock:
            return self._latest_snapshot

    def mjpeg_frames(self) -> Iterator[bytes]:
        """Yield latest JPEGs in multipart MJPEG format for Flask /video.

        Return: an infinite bytes iterator while the program runs. Edge case:
        it waits until the first camera frame exists. Source: official Flask
        streaming-response pattern using a generator.
        """
        previous_frame: Optional[bytes] = None
        while self._running.is_set():
            with self._lock:
                jpeg = self._latest_jpeg
            if jpeg is None or jpeg is previous_frame:
                time.sleep(0.03)
                continue
            previous_frame = jpeg
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

    def _capture_loop(self) -> None:
        """Capture, detect, annotate, and cache frames until asked to stop.

        Why: this producer loop keeps vision independent from browser traffic.
        Edge case: a single frame error is logged and retried, not fatal.
        Interview explanation: "The stream is a cached output of the vision
        loop, so opening multiple dashboard tabs does not open multiple cameras."
        """
        while self._running.is_set():
            try:
                assert self._camera is not None
                frame_rgb = self._camera.capture_array("main")
                annotated, snapshot = self._detect_and_annotate(frame_rgb)
                success, encoded = cv2.imencode(".jpg", annotated)
                if success:
                    with self._lock:
                        self._latest_jpeg = encoded.tobytes()
                        self._latest_snapshot = snapshot
            except Exception:  # Camera glitches should not kill the whole cane.
                LOGGER.exception("Vision frame failed; retrying")
                time.sleep(0.2)

    def _detect_and_annotate(self, frame_rgb: np.ndarray) -> tuple[np.ndarray, VisionSnapshot]:
        """Run MobileNet SSD on one frame and draw accepted person/chair boxes.

        Parameters: RGB camera frame. Return: BGR JPEG-ready frame and flags.
        Important logic: only person/chair predictions over the confidence
        threshold are kept. Source: official OpenCV DNN Caffe/blob/forward API.
        """
        assert self._network is not None
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        height, width = frame_bgr.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame_bgr, 0.007843, (300, 300), 127.5, swapRB=False, crop=False
        )
        self._network.setInput(blob)
        detections = self._network.forward()
        found = {"person": False, "chair": False}

        for detection in detections[0, 0]:
            confidence = float(detection[2])
            class_id = int(detection[1])
            if confidence < self._confidence_threshold or class_id >= len(CLASS_NAMES):
                continue
            label = CLASS_NAMES[class_id]
            if label not in INTERESTING_CLASSES:
                continue

            found[label] = True
            x1, y1, x2, y2 = (detection[3:7] * np.array([width, height, width, height])).astype(int)
            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame_bgr, f"{label}: {confidence:.0%}", (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2,
            )

        return frame_bgr, VisionSnapshot(person=found["person"], chair=found["chair"])


# remeber NOTES
# Q: Why cache JPEG frames instead of running detection in the /video route?
# A: The vision worker should run once per camera frame; otherwise each browser
#    could start costly duplicate ML inference and contend for the camera.
# Call map: main -> start/stop; alert/web -> latest_snapshot/mjpeg_frames;
# the worker thread -> _capture_loop -> _detect_and_annotate.
# Remember: MobileNet SSD identifies person/chair only; stairs use sensors.py.
