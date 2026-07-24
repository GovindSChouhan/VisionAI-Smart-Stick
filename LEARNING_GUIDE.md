<!--
Purpose: Beginner-friendly explanation of SmartStick's full runtime flow.
Interview Explanation: "I documented not only what the code does but why the
modules are separated, so another developer can maintain it safely."
Key Concepts: program lifecycle, producer-consumer workers, API data flow,
priority rules, debugging.
Important Things to Remember: Run main.py on the Raspberry Pi; Windows is for
editing and syntax checking unless a separate simulation mode is later built.
Dependencies: See README.md for the complete dependency table.
Source: Project-specific documentation; library sources are linked in README.
-->

# SmartStick learning guide

## Dependency flow

```text
You run: python3 main.py --floor-distance 82
                 │
                 ▼
main.py creates SensorManager, VisionSystem, AlertDispatcher, SharedState
                 │
        ┌────────┼───────────────────┐
        ▼        ▼                   ▼
sensor loop   vision thread       alert loop
sensors.py    vision.py           alerts.py
reads GPIO    captures camera     reads latest snapshots
creates       detects person/     chooses one highest-priority
SensorSnapshot chair and caches   message; espeak → aplay speaks it
              JPEG/VisionSnapshot
        │        │
        └────┬───┘
             ▼
web.py creates Flask routes
  /         → index.html
  /sensors  → latest JSON data
  /video    → cached annotated MJPEG frames
             ▼
Browser: index.html fetches /sensors every second and displays /video
```

## File responsibilities

| File | Depends on | Depended on by | Why it exists |
|---|---|---|---|
| `main.py` | All Python modules | Python entry-point | Creates modules, starts workers, owns shutdown. |
| `sensors.py` | RPi.GPIO, time | main, alerts, web | Turns echo timing into distances and flags. |
| `vision.py` | Picamera2, cv2, NumPy | main, alerts, web | Owns one camera and detects person/chair. |
| `alerts.py` | snapshots, subprocess | main | Chooses one safe voice message. |
| `web.py` | Flask, snapshots, vision | main | Provides monitoring routes only. |
| `index.html` | `/sensors`, `/video` | browser | Displays the data without making safety decisions. |

## Important function map

| Function | Called by | Feature depending on it |
|---|---|---|
| `main()` | Python entry-point guard | Complete lifecycle. |
| `sensor_loop()` | `main()` worker thread | Repeated GPIO readings. |
| `SensorManager.read_snapshot()` | `sensor_loop()` | Obstacle/stair flags. |
| `UltrasonicSensor.read_distance_cm()` | `read_snapshot()` | Time-of-flight measurement. |
| `VisionSystem.start()` | `main()` | Camera/model startup. |
| `VisionSystem._capture_loop()` | vision worker thread | Cached frames/detection flags. |
| `VisionSystem._detect_and_annotate()` | `_capture_loop()` | MobileNet person/chair detection. |
| `AlertDispatcher.run()` | `main()` alert thread | Continuous alert evaluation. |
| `AlertDispatcher.choose_message()` | `run()` | Priority safety policy. |
| `AlertDispatcher.speak_if_allowed()` | `run()` | Cooldown/no overlapping speech. |
| `create_app()` | `main()` | Flask routes. |
| `pollSensors()` | browser on load and interval | Dashboard updates. |

## Debugging checklist on the Pi

1. **Program stops immediately:** read the first traceback. Missing model files,
   missing Picamera2, or GPIO permissions/wiring are common causes.
2. **No dashboard:** run `hostname -I`; use that IP, port `5000`, and confirm
   your phone/laptop is on the same Wi-Fi.
3. **Dashboard works but camera is blank:** test the Pi camera using a standard
   Pi OS camera command first; then confirm both model files are in `models/`.
4. **No ultrasonic data:** re-check BCM pin numbers, common ground, ECHO level
   shifting, and the `--floor-distance` calibration.
5. **No sound:** run `espeak "test"`, check the selected audio output, then
   test with headphones connected.
6. **Too many warnings:** raise the relevant threshold/tolerance slowly and
   test again in a controlled environment.

## Interview recap

**Why not put everything in one file?** Separate modules reduce risk. Hardware
timing, AI inference, audio policy, and HTTP requests change for different
reasons and should be testable independently.

**What happens when the browser closes?** The sensor, vision, and alert workers
continue. Flask is only a monitoring interface.

**How is a dangerous warning selected?** An ordered function returns the first
active hazard; because it returns one string, speech cannot contain competing
warnings.

**Source honesty:** The application structure and safety rules are project
code. Library calls use documented APIs from Raspberry Pi, OpenCV, Flask,
RPi.GPIO, and MDN, identified in the relevant file headers. Do not claim to
have trained MobileNet SSD; describe it as a pretrained Caffe model.
