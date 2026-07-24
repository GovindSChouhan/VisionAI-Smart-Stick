"""

main.py → Main entry point (starts everything)
web.py → Runs the web server/dashboard
vision.py → Pi Camera + MobileNet SSD processing
sensors.py → Ultrasonic sensors
alerts.py → Audio alerts

Purpose: SmartStick's single entry point; starts hardware workers and Flask.
Explanation: "main.py is the composition root. It creates each
  focused module, shares safe snapshots between them, starts background loops,
  and performs clean shutdown on Ctrl+C."
Key Concepts: composition root, threads, immutable snapshots, locking, graceful
  shutdown, command-line arguments.
Important Things to Remember: Run this file only on the Raspberry Pi after
  installing dependencies and copying model files. Stop with Ctrl+C.
Dependencies: every local module plus their dependencies.
Why This File Exists: It is the one place that composes modules and controls
  startup/shutdown; the feature logic deliberately remains in the other files.
Depends On: sensors.py, vision.py, alerts.py, web.py, and standard threading.
Depended On By: nobody. Python invokes it through the __main__ entry-point guard.

Source notes: argparse, threading.Event, dataclasses, and signal-style
KeyboardInterrupt handling are Python standard-library/common patterns. No code
in this file is copied from an external project.
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from alerts import AlertDispatcher
from sensors import SensorManager, SensorSnapshot
from vision import VisionSystem
from web import create_app

PROJECT_DIR = Path(__file__).resolve().parent
SENSOR_INTERVAL_SECONDS = 1.0


def empty_sensor_snapshot() -> SensorSnapshot:
    """Return safe initial state before the first physical reading.

    Return: no distances and all flags false. Why: Flask/alerts can start
    before a sensor loop completes. Interview explanation: "Default values
    prevent race-condition crashes at startup."
    """
    return SensorSnapshot(None, None, None, False, False, False, False)


@dataclass
class SharedState:
    """Thread-safe holder for the newest immutable sensor snapshot."""

    _sensors: SensorSnapshot = field(default_factory=empty_sensor_snapshot)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update_sensors(self, snapshot: SensorSnapshot) -> None:
        """Replace the last sensor state atomically. Parameter: new snapshot."""
        with self._lock:
            self._sensors = snapshot

    def sensors(self) -> SensorSnapshot:
        """Return latest sensor snapshot safely. Return: immutable snapshot."""
        with self._lock:
            return self._sensors


def sensor_loop(manager: SensorManager, state: SharedState, running: threading.Event) -> None:
    """Read sensors regularly and publish each complete snapshot.

    Parameters: configured manager, shared state, and stop event. Return: none.
    Why: GPIO timing must not run in Flask's request thread. Edge case: a
    reading error logs and retries rather than ending the application.
    Interview explanation: "One sensor worker produces snapshots consumed by
    the alert engine and dashboard."
    """
    while running.is_set():
        try:
            state.update_sensors(manager.read_snapshot())
        except Exception:
            logging.exception("Sensor reading failed; retrying")
        time.sleep(SENSOR_INTERVAL_SECONDS)


def parse_arguments() -> argparse.Namespace:
    """Read safe, optional startup settings from the command line.

    Return: parsed arguments. --floor-distance supports real-world calibration
    without editing source code. Source: Python standard-library argparse API.
    """
    parser = argparse.ArgumentParser(description="Run the SmartStick server.")
    parser.add_argument("--floor-distance", type=float, default=82.0, metavar="CM")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    """Start SmartStick and keep it alive until Ctrl+C.

    Return: none. Important sequence: GPIO, camera/model, background workers,
    then Flask. This order reveals hardware/model errors before the dashboard
    claims to be ready. Interview explanation: "The entry point composes
    independent modules and owns their lifecycle."
    """
    args = parse_arguments()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    running = threading.Event()
    running.set()
    state = SharedState()
    sensors = SensorManager(normal_floor_distance_cm=args.floor_distance)
    vision = VisionSystem(PROJECT_DIR / "models")
    alerts = AlertDispatcher()

    try:
        sensors.setup()
        vision.start()
        sensor_thread = threading.Thread(
            target=sensor_loop, args=(sensors, state, running),
            name="sensor-loop", daemon=True,
        )
        alert_thread = threading.Thread(
            target=alerts.run,
            args=(state.sensors, vision.latest_snapshot, running.is_set),
            name="alert-loop", daemon=True,
        )
        sensor_thread.start()
        alert_thread.start()

        app = create_app(PROJECT_DIR, state.sensors, vision.latest_snapshot, vision)
        logging.info("Dashboard: http://%s:%s", args.host, args.port)
        app.run(host=args.host, port=args.port, threaded=True, debug=False)
    except KeyboardInterrupt:
        logging.info("Stopping SmartStick")
    finally:
        running.clear()
        vision.stop()
        sensors.cleanup()


if __name__ == "__main__":
    # Standard Python entry-point guard: importing this file never starts hardware.
    main()


#  NOTES
# Q: Why should I run python3 main.py instead of flask run?
# A: main.py starts the GPIO, camera, sensor loop, alert loop, and Flask app;
#    Flask alone cannot make the physical cane work.
# Call map: Python guard -> main; main -> parse_arguments, sensor_loop thread,
# alerts.run thread, and web.create_app; sensor_loop -> read_snapshot.
# Remember: Ctrl+C reaches finally, which stops the camera and cleans up GPIO.
