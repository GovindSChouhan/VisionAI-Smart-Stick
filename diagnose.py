"""
Purpose: Check whether a Raspberry Pi has everything SmartStick needs to start.
Interview Explanation: "Before debugging the full application, I run a small
preflight check that validates Python imports, OS audio commands, and required
model files. This separates installation problems from runtime problems."
Key Concepts: deployment preflight, import checks, file checks, exit statuses.
Important Things to Remember: Run this on the Pi after installation, before
running main.py. It checks availability; it does not prove wiring is correct.
Dependencies: Python standard library; checks optional Pi packages by import.
Why This File Exists: Hardware projects otherwise fail late with unclear errors.
Depends On: installed Pi OS packages, pip packages, and models/ files.
Depended On By: a developer manually runs `python3 diagnose.py`.

Source: Python standard-library importlib, shutil.which, pathlib, and sys APIs.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
MODEL_FILES = ("MobileNetSSD_deploy.prototxt", "MobileNetSSD_deploy.caffemodel")
PYTHON_MODULES = {
    "flask": "pip install -r requirements.txt",
    "numpy": "sudo apt install python3-opencv",
    "cv2": "sudo apt install python3-opencv",
    "picamera2": "sudo apt install python3-picamera2",
    "RPi.GPIO": "sudo apt install python3-rpi.gpio",
}
COMMANDS = {"espeak": "sudo apt install espeak", "aplay": "sudo apt install alsa-utils"}


def check_python_modules() -> list[str]:
    """Import each required module and return human-readable failures.

    Called by: main(). Return: installation messages; empty means imports work.
    Feature: verifies Flask, vision, and GPIO dependencies before main.py runs.
    Source: standard Python importlib pattern.
    """
    failures: list[str] = []
    for module_name, installation_hint in PYTHON_MODULES.items():
        try:
            importlib.import_module(module_name)
            print(f"PASS Python module: {module_name}")
        except ImportError:
            failures.append(f"Missing {module_name}: {installation_hint}")
    return failures


def check_model_files() -> list[str]:
    """Confirm both separately downloaded MobileNet SSD files exist.

    Called by: main(). Return: missing-file messages or an empty list. Why: the
    Caffe network cannot load without both architecture and weights files.
    Edge case: filenames are case-sensitive on Pi OS. Feature: vision startup.
    """
    failures: list[str] = []
    for filename in MODEL_FILES:
        path = PROJECT_DIR / "models" / filename
        if path.is_file():
            print(f"PASS Model file: models/{filename}")
        else:
            failures.append(f"Missing model file: models/{filename}")
    return failures


def check_audio_commands() -> list[str]:
    """Confirm the executable names used by alerts.py are on PATH.

    Called by: main(). Return: missing-command messages or an empty list.
    Source: Python standard-library shutil.which pattern. Feature: voice alerts.
    """
    failures: list[str] = []
    for command, installation_hint in COMMANDS.items():
        if shutil.which(command):
            print(f"PASS Audio command: {command}")
        else:
            failures.append(f"Missing {command}: {installation_hint}")
    return failures


def main() -> int:
    """Run all non-invasive checks and return a shell-friendly status code.

    Called by: Python entry-point guard. Return: 0 ready, 1 action needed.
    Interview explanation: "I made deployment checks repeatable and explicit."
    """
    print("SmartStick preflight check")
    failures = check_python_modules() + check_model_files() + check_audio_commands()
    if failures:
        print("\nNOT READY — fix these items:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nREADY — dependencies and model files are present.")
    print("Next: verify wiring, then run: python3 main.py --floor-distance 82")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


#W NOTES
# Q: Why not let main.py discover missing packages itself?
# A: It does report startup errors, but a separate preflight gives a clear,
# complete checklist before hardware workers begin.
# Remember: a PASS result does not validate sensor wiring or camera focus.
