"""
Purpose: Provide the local Flask dashboard and its three HTTP routes.
 NOte remebrt: "Flask exposes the latest state, not the hardware
  itself: / serves the dashboard, /sensors serves JSON, and /video streams
  cached JPEG frames as MJPEG."
Key Concepts: Flask routes, JSON API, MJPEG multipart streaming, dependency
  injection through callbacks.
Important Things to Remember: Flask is optional monitoring; core sensing and
  alerts run in background threads even if no browser is open.
Dependencies: Flask, SensorSnapshot, VisionSnapshot, VisionSystem.
Why This File Exists: It keeps HTTP/browser concerns separate from GPIO, ML,
  and voice-alert safety logic.
Depends On: Flask plus callback functions supplied by main.py.
Depended On By: main.py calls create_app; index.html calls its routes.

Source notes: Flask's Response(generator, mimetype=...) streaming pattern is
based on the official Flask Streaming Contents documentation. Flask jsonify is
the official JSON response helper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from flask import Flask, Response, jsonify, send_from_directory

from sensors import SensorSnapshot
from vision import VisionSnapshot, VisionSystem


def create_app(
    project_dir: Path,
    get_sensors: Callable[[], SensorSnapshot],
    get_vision: Callable[[], VisionSnapshot],
    vision_system: VisionSystem,
) -> Flask:
    """Build and return the Flask application without starting the server.

    Parameters: project path for index.html; callbacks for fresh state; vision
    system for the MJPEG generator. Return: configured Flask app. Why: passing
    dependencies in makes the routes simple and avoids global hardware state.
    Interview explanation: "The web layer reads shared state; it does not run
    GPIO or machine learning itself."
    """
    app = Flask(__name__)

    @app.get("/")
    def dashboard() -> Response:
        """Serve the one static dashboard page. Return: index.html response."""
        return send_from_directory(project_dir, "index.html")

    @app.get("/video")
    def video() -> Response:
        """Stream cached annotated camera frames as multipart MJPEG.

        Return: a long-lived response. Source: official Flask generator-based
        streaming pattern. The boundary must match the generator in vision.py.
        """
        return Response(
            vision_system.mjpeg_frames(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/sensors")
    def sensors() -> Response:
        """Return latest distances and all safety flags as JSON.

        Return: JSON response. None distances become JSON null, so the browser
        can display an unavailable sensor honestly instead of a fake number.
        """
        sensor_data = get_sensors()
        vision_data = get_vision()
        return jsonify(
            left=sensor_data.left_cm,
            right=sensor_data.right_cm,
            down=sensor_data.down_cm,
            person=vision_data.person,
            chair=vision_data.chair,
            stair_up=sensor_data.stair_up,
            stair_down=sensor_data.stair_down,
            left_obstacle=sensor_data.left_obstacle,
            right_obstacle=sensor_data.right_obstacle,
        )

    return app


# Remember NOTES
# Q: Why use callbacks (get_sensors/get_vision) rather than global variables?
# A: The web layer receives only the latest state it needs, making dependencies
#    explicit and preventing Flask routes from owning hardware objects.
# Call map: main -> create_app; Flask calls dashboard/video/sensors on HTTP requests.
# Remember: /video is MJPEG; /sensors is JSON; / is the dashboard HTML.
