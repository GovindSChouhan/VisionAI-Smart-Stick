"""
Purpose: Choose one highest-priority safety message and speak it non-blockingly.
 Explanation: "The alert engine is a safety arbitration layer. It
  converts many simultaneous sensor/AI signals into one understandable spoken
  instruction, always prioritising the greatest immediate risk."    
Key Concepts: priority rules, cooldowns, non-blocking subprocesses, polling.
Important Things to Remember: stairs suppress obstacle alerts automatically
  because a stair rule wins first. Audio must never overlap.    
Dependencies: espeak and aplay installed on Raspberry Pi OS; Python standard
  library; SensorSnapshot and VisionSnapshot from this project.
Why This File Exists: All warning priority and audio timing live in one
  reviewable safety-policy module rather than scattered through sensor code.
Depends On: sensors.py/vision.py snapshots and Python subprocess/time.
Depended On By: main.py starts its worker thread.

Source notes: subprocess.Popen is the documented Python standard-library API.
The priority-selector and cooldown are common implementation patterns, written
for this project rather than copied from a specific external source.     
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Callable, Optional

from sensors import SensorSnapshot
from vision import VisionSnapshot

LOGGER = logging.getLogger(__name__)


class AlertDispatcher:
    """Continuously choose and speak exactly one appropriate warning."""

    COOLDOWN_SECONDS = 3.0

    def __init__(self, cooldown_seconds: float = COOLDOWN_SECONDS) -> None:
        """Create an audio dispatcher.

        Parameters: cooldown_seconds limits repeated warnings. Return: none.
        Why: speech that repeats without pause is distracting and masks new
        hazards. Interview explanation: "A cooldown makes the interface usable
        rather than noisy."
        """
        self._cooldown_seconds = cooldown_seconds
        self._last_spoken_at = 0.0
        self._speech_process: Optional[subprocess.Popen[bytes]] = None
        self._audio_process: Optional[subprocess.Popen[bytes]] = None

    def run(
        self,
        get_sensors: Callable[[], SensorSnapshot],
        get_vision: Callable[[], VisionSnapshot],
        is_running: Callable[[], bool],
    ) -> None:
        """Poll latest state and request speech until the application stops.

        Parameters: callbacks return the latest state without sharing mutable
        variables; is_running controls graceful shutdown. Return: none.
        Important logic: the alert is selected before speaking. Interview
        explanation: "The dispatcher is independent, so audio cannot block
        sensor or Flask processing."
        """
        while is_running():
            self._is_speaking()  # Also reaps a finished espeak child process.
            message = self.choose_message(get_sensors(), get_vision())
            if message is not None:
                self.speak_if_allowed(message)
            time.sleep(0.1)

    @staticmethod
    def choose_message(sensors: SensorSnapshot, vision: VisionSnapshot) -> Optional[str]:
        """Return the single highest-priority warning, or None when safe.

        Parameters: newest sensor and object-detection snapshots. Return: text
        for espeak or None. Important logic: order is the project safety policy:
        downward stair, upward stair, person, chair, then side obstacle.
        Edge case: left/right alerts are intentionally unreachable during stairs
        because stair conditions return first. Interview explanation: "This is
        deterministic priority-based sensor fusion, not random simultaneous AI."
        """
        if sensors.stair_down:
            return "Downward stairs ahead"
        if sensors.stair_up:
            return "Upward stairs ahead"
        if vision.person:
            return "Person ahead"
        if vision.chair:
            return "Chair ahead"
        if sensors.left_obstacle and sensors.right_obstacle:
            return "Obstacle on both sides"
        if sensors.left_obstacle:
            return "Obstacle on the left"
        if sensors.right_obstacle:
            return "Obstacle on the right"
        return None

    def speak_if_allowed(self, message: str) -> None:
        """Start espeak -> aplay only if no audio is active and cooldown passed.

        Parameters: message is a trusted, code-defined alert string. Return:
        none. Edge cases: missing audio programs are logged; no shell is used,
        so text is not treated as a command. Interview explanation: "I use two
        non-blocking processes, so spoken audio cannot freeze the safety loop."
        """
        now = time.monotonic()
        if self._is_speaking() or now - self._last_spoken_at < self._cooldown_seconds:
            return
        try:
            self._speech_process = subprocess.Popen(
                ["espeak", "--stdout", message], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            self._audio_process = subprocess.Popen(
                ["aplay"], stdin=self._speech_process.stdout,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            assert self._speech_process.stdout is not None
            self._speech_process.stdout.close()  # Let aplay receive EOF when espeak finishes.
            self._last_spoken_at = now
        except FileNotFoundError:
            LOGGER.error("Audio unavailable: install espeak and alsa-utils (aplay).")

    def _is_speaking(self) -> bool:
        """Return whether the current aplay process is still running.

        Return: True while audio owns the speaker. This small helper enforces
        the project's "one alert at a time" rule.
        """
        if self._speech_process is not None:
            self._speech_process.poll()  # Reap a completed espeak process.
        return self._audio_process is not None and self._audio_process.poll() is None


#  NOTES
# Q: How do you prevent conflicting alerts?
# A: choose_message returns the first active rule in an explicit danger order;
#    speak_if_allowed also prevents overlap and enforces a three-second cooldown.
# Call map: main's alert thread -> run -> choose_message and speak_if_allowed;
# speak_if_allowed/run -> _is_speaking.
# Remember: this is deterministic, rule-based sensor fusion—not a second ML model.
