"""
Purpose: Read the three ultrasonic sensors and classify obstacles and stairs.
Interview Explanation: "This module converts ultrasonic echo times into safe,
  simple distance flags. It is independent from audio and Flask, so it is easy
  to test and change without breaking the rest of the cane."
Key Concepts: GPIO (BCM numbering), time-of-flight distance measurement,
  timeout handling, sensor cross-talk prevention, configurable thresholds.
Important Things to Remember: HC-SR04 ECHO is normally 5 V; each ECHO wire
  must be level-shifted to 3.3 V before reaching a Raspberry Pi GPIO input.
Dependencies: RPi.GPIO on Raspberry Pi OS; Python standard library elsewhere.
Why This File Exists: It keeps low-level hardware timing out of main.py.
Depends On: RPi.GPIO and Python time/dataclasses.
Depended On By: main.py reads snapshots; alerts.py and web.py use their fields.

Source notes: RPi.GPIO's documented GPIO.setmode(GPIO.BCM), setup, input,
output and cleanup pattern. The distance formula is the standard ultrasonic
time-of-flight calculation: distance = (time x speed of sound) / 2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    import RPi.GPIO as GPIO
except ImportError:  # Lets the file be read/checked on a non-Raspberry-Pi PC.
    GPIO = None


# GPIO numbers use BCM numbering, not the physical pin numbers on the header.
LEFT_TRIG, LEFT_ECHO = 23, 24
RIGHT_TRIG, RIGHT_ECHO = 17, 27
DOWN_TRIG, DOWN_ECHO = 6, 5


@dataclass(frozen=True)
class SensorSnapshot:
    """One safe-to-share copy of the latest sensor state."""

    left_cm: Optional[float]
    right_cm: Optional[float]
    down_cm: Optional[float]
    left_obstacle: bool
    right_obstacle: bool
    stair_up: bool
    stair_down: bool


class UltrasonicSensor:
    """Reads one ultrasonic sensor using its trigger and echo GPIO pins."""

    SPEED_OF_SOUND_CM_S = 34_300

    def __init__(self, trigger_pin: int, echo_pin: int) -> None:
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin

    def setup(self) -> None:
        """Configure this sensor's pins after GPIO mode has been selected.

        Why: GPIO pins are inputs by default; trigger must be an output and
        echo must be an input. Parameters/return: none. Edge case: setup is
        intentionally performed once, before any readings.
        Interview explanation: "I explicitly configure each hardware pin so
        the software matches the wiring diagram."
        """
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trigger_pin, GPIO.LOW)

    def read_distance_cm(self, timeout_s: float = 0.03) -> Optional[float]:
        """Return distance in centimetres, or None if no echo arrives in time.

        An ultrasonic pulse travels to the object and back, so the measured
        travel time is divided by two when converting it to distance.

        Parameters: timeout_s is the maximum wait for either echo edge.
        Return: rounded centimetres, or None for a missing/invalid echo.
        Important logic: two loops wait for echo HIGH then echo LOW.
        Edge cases: timeout and implausible readings become None rather than
        false obstacle warnings. Interview explanation: "I fail safely by
        rejecting a bad sensor reading instead of treating it as a real object."
        """
        GPIO.output(self.trigger_pin, GPIO.HIGH)
        time.sleep(0.00001)  # 10 microsecond trigger pulse
        GPIO.output(self.trigger_pin, GPIO.LOW)

        deadline = time.monotonic() + timeout_s
        while GPIO.input(self.echo_pin) == GPIO.LOW:
            if time.monotonic() > deadline:
                return None

        pulse_started = time.monotonic()
        deadline = pulse_started + timeout_s
        while GPIO.input(self.echo_pin) == GPIO.HIGH:
            if time.monotonic() > deadline:
                return None

        pulse_seconds = time.monotonic() - pulse_started
        distance_cm = (pulse_seconds * self.SPEED_OF_SOUND_CM_S) / 2

        # Ignore physically implausible readings instead of creating false alerts.
        return round(distance_cm, 1) if 2 <= distance_cm <= 400 else None


class SensorManager:
    """Coordinates the three sensors and turns readings into safety flags."""

    OBSTACLE_DISTANCE_CM = 50.0

    def __init__(
        self,
        normal_floor_distance_cm: float = 82.0,
        stair_change_cm: float = 12.0,
    ) -> None:
        """Create the manager.

        ``normal_floor_distance_cm`` is measured after mounting the downward
        sensor.  ``stair_change_cm`` is a safety margin: small normal movement
        inside this range does not count as a stair.
        """
        self.normal_floor_distance_cm = normal_floor_distance_cm
        self.stair_change_cm = stair_change_cm
        self.left_sensor = UltrasonicSensor(LEFT_TRIG, LEFT_ECHO)
        self.right_sensor = UltrasonicSensor(RIGHT_TRIG, RIGHT_ECHO)
        self.down_sensor = UltrasonicSensor(DOWN_TRIG, DOWN_ECHO)

    def setup(self) -> None:
        """Prepare every GPIO pin. Call once when the program starts.

        Parameters/return: none. It raises RuntimeError on a non-Pi machine
        instead of failing later with an unclear GPIO error. Interview
        explanation: "Hardware setup is centralized, making startup explicit."
        """
        if GPIO is None:
            raise RuntimeError(
                "RPi.GPIO is unavailable. Run SmartStick on a Raspberry Pi."
            )

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.left_sensor.setup()
        self.right_sensor.setup()
        self.down_sensor.setup()
        time.sleep(0.05)  # Allows the sensors' electronics to settle.

    def read_snapshot(self) -> SensorSnapshot:
        """Take one sequential reading from each sensor and classify it.

        Return: a SensorSnapshot containing raw distances and Boolean flags.
        Important logic: readings are sequential to prevent ultrasonic
        cross-talk; a larger down distance means a downward drop, while a
        smaller one means an upward step. Edge case: a None distance never
        triggers an alert. Interview explanation: "I keep measurement and
        decision rules together, then pass a clean snapshot to other modules."
        """
        # Read sequentially so ultrasonic pulses from different sensors do not
        # interfere with one another.
        left_cm = self.left_sensor.read_distance_cm()
        right_cm = self.right_sensor.read_distance_cm()
        down_cm = self.down_sensor.read_distance_cm()

        left_obstacle = left_cm is not None and left_cm < self.OBSTACLE_DISTANCE_CM
        right_obstacle = right_cm is not None and right_cm < self.OBSTACLE_DISTANCE_CM

        stair_up = False
        stair_down = False
        if down_cm is not None:
            if down_cm > self.normal_floor_distance_cm + self.stair_change_cm:
                stair_down = True  # Ground moved farther away: a drop/down-step.
            elif down_cm < self.normal_floor_distance_cm - self.stair_change_cm:
                stair_up = True  # Ground moved closer: a raised/up-step.

        return SensorSnapshot(
            left_cm=left_cm,
            right_cm=right_cm,
            down_cm=down_cm,
            left_obstacle=left_obstacle,
            right_obstacle=right_obstacle,
            stair_up=stair_up,
            stair_down=stair_down,
        )

    @staticmethod
    def cleanup() -> None:
        """Release GPIO pins during normal shutdown.

        Why: prevents pins from being left configured after Ctrl+C. Parameters
        and return: none. Source: documented RPi.GPIO cleanup pattern.
        """
        if GPIO is not None:
            GPIO.cleanup()


# INTERVIEW NOTES
# Q: Why read the three ultrasonic sensors sequentially?
# A: Simultaneous ultrasonic pulses can hear one another's echoes (cross-talk),
#    so sequential readings are slower but substantially safer and clearer.
# Call map: SensorManager.setup -> UltrasonicSensor.setup; sensor_loop ->
# SensorManager.read_snapshot -> UltrasonicSensor.read_distance_cm; main -> cleanup.
# Remember: GPIO numbers here are BCM numbers; ECHO must be reduced to 3.3 V.
