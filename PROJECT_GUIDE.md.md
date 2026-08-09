<!--
Purpose: Setup, operation, calibration, architecture, and interview guide.
Interview Explanation: "This README makes the project reproducible: another
person can wire, install, calibrate, run, and understand SmartStick."
Key Concepts: Raspberry Pi deployment, virtual environments, GPIO safety,
calibration, local web server, systemd service.
Important Things to Remember: This is Python only. There is no npm, Node.js,
package.json, or JavaScript build step.
Dependencies: Raspberry Pi OS, Python, Picamera2, audio tools, model files.
Source notes: Links in References are official library/vendor documentation.
--comment>

# SmartStick

SmartStick is a Raspberry Pi 4 assistive-navigation cane prototype. It combines
three ultrasonic sensors, a Raspberry Pi Camera Module, MobileNet SSD object
detection, priority-based voice warnings, and a local Flask monitoring page.

> Safety note: this is a prototype, not a certified mobility aid. Test in a
> controlled environment with a sighted assistant before relying on it.

## What it does

1. Measures left and right obstacles with ultrasonic sensors. An object under
   **50 cm** is considered an obstacle.
2. Measures the floor with a downward-facing ultrasonic sensor. A noticeably
   larger distance means a downward stair/drop; a smaller distance means an
   upward stair.
3. Uses MobileNet SSD to detect **person** and **chair** in Pi Camera frames.
4. Speaks only one warning at a time, with this safety priority:

   ```text
   Downward stair/drop → Upward stair → Person → Chair → Side obstacle
   ```

5. Serves a local dashboard with `/`, `/video`, and `/sensors`.

## Project files

```text
SmartStick/
├── main.py              # The only file you run
├── sensors.py           # GPIO, ultrasonic distances, stair/drop flags
├── vision.py            # Picamera2, MobileNet SSD, annotated JPEG frames
├── alerts.py            # Safety priority and non-blocking voice audio
├── web.py               # Flask routes
├── index.html           # Plain browser dashboard (no Node/npm)
├── requirements.txt     # pip packages
├── LEARNING_GUIDE.md    # Full startup flow, call map, debugging, interview help
├── diagnose.py          # Pi installation/model/audio preflight check
├── DEPLOYMENT.md        # GitHub showcase and safe edge deployment guidance
├── models/              # Put the two MobileNet SSD files here
│   └── .gitkeep
└── README.md             # This guide
```

Every code file begins with an interview-focused documentation header and every
important function has a detailed docstring. Read them from `sensors.py` through
`main.py` in that order.

## Exactly how to run it

### The one entry point: `main.py`

Run **only** `main.py`. It is the composition root: it creates the sensor,
vision, alert, and Flask modules, starts their workers, and cleans up GPIO when
you stop it.

Do **not** run `web.py`; it only defines Flask routes and has no startup code.
Do **not** use `flask run`; it would start Flask without starting your camera,
sensors, or alert workers. Do **not** use Node/npm commands; this is Python.

### Windows / VS Code commands

This is Raspberry Pi hardware software. It cannot run the real camera, GPIO,
ultrasonic sensors, or audio output on Windows. Use Windows to open, read,
edit, and syntax-check the files:

```powershell
cd C:\Users\pc\Documents\Codex\2026-07-23\c-users-pc-downloads-smartstick-index\outputs\SmartStick\SmartStick\VisionAi
code .
py -m py_compile main.py sensors.py vision.py alerts.py web.py
```

The final command checks Python syntax only; it does not test hardware. Do not
install/run this project's Pi dependencies on Windows expecting the cane to
work. In VS Code, the best setup is **Remote - SSH** connected to the Pi, so
the terminal runs on the Pi while the editor remains on your Windows PC.

### Raspberry Pi commands (the real run)

```bash
cd ~/SmartStick
source venv/bin/activate
python3 main.py --floor-distance 82
```

Expected terminal output includes a line similar to:

```text
Dashboard: http://0.0.0.0:5000
 * Serving Flask app 'web'
```

Find the Pi IP address with `hostname -I`, then open this from a phone/laptop
on the same Wi-Fi:

```text
http://YOUR_PI_IP:5000
```

For example: `http://192.168.1.50:5000`. The page shows the annotated camera
feed and current sensor cards. Press `Ctrl+C` in the Pi terminal to stop.

## Environment variables (`.env`)

This version uses **no environment variables** and does **not** need a `.env`
file. Values that must be adjusted in the field are intentionally visible:

- `--floor-distance 82` — passed to `main.py` at run time for calibration.
- `OBSTACLE_DISTANCE_CM = 50.0` — in `sensors.py`.
- `stair_change_cm = 12.0` — default in `SensorManager` in `sensors.py`.
- `COOLDOWN_SECONDS = 3.0` — in `alerts.py`.
- `confidence_threshold = 0.50` — default in `vision.py`.

There are no hidden API keys, database credentials, or Mapbox tokens. Mapbox is
not part of the current core project. If it is added later, its token and GPS
configuration should be documented before introducing a `.env` file.

## Dependencies explained

| Dependency | Why it is needed | Imported/used by | If removed | Required? |
|---|---|---|---|---|
| `Flask` | Provides local HTTP routes and JSON/MJPEG responses. | `web.py` | Dashboard, `/sensors`, and `/video` will not start; sensing/audio can still run. | Required for dashboard |
| `NumPy` (`python3-opencv` dependency) | Multiplies model output coordinates by frame dimensions. | `vision.py` | Vision detection cannot convert model boxes into pixel positions. | Required for vision |
| `OpenCV` (`python3-opencv`, imported as `cv2`) | Loads the Caffe model, runs inference, draws boxes, encodes JPEG. | `vision.py` | Person/chair detection and video stream fail. | Required for vision |
| `RPi.GPIO` (`python3-rpi.gpio`) | Controls GPIO trigger pins and reads echo pins. | `sensors.py` | Ultrasonic obstacle/stair sensing fails. | Required on Pi |
| `picamera2` (installed with `apt`) | Captures frames from the official Pi Camera stack. | `vision.py` | Camera, AI, and `/video` fail. | Required for vision |
| `espeak` (installed with `apt`) | Converts alert text to spoken WAV audio. | `alerts.py` | No spoken alerts. | Required for audio |
| `aplay` from `alsa-utils` (installed with `apt`) | Sends generated WAV audio to the selected Pi audio output. | `alerts.py` | No headphone-jack playback. | Required for audio |

`requirements.txt` contains only packages installed by `pip`. Camera, GPIO,
OpenCV, NumPy, and audio tools are Pi OS packages, so they are documented in
the installation commands rather than falsely placed in `requirements.txt`.

## Hardware wiring

All numbers below are **BCM GPIO numbers**, not physical header pin numbers.

| Sensor | TRIG | ECHO | Role |
|---|---:|---:|---|
| Left ultrasonic | GPIO23 | GPIO24 | Left obstacle distance |
| Right ultrasonic | GPIO17 | GPIO27 | Right obstacle distance |
| Down-facing ultrasonic | GPIO6 | GPIO5 | Stair/drop distance |
| Pi Camera Module | CSI connector | CSI connector | Vision input |

### Critical electrical safety

Most HC-SR04-style ultrasonic sensors run at 5 V and drive **ECHO at 5 V**.
Raspberry Pi GPIO inputs accept **3.3 V only**. Put a voltage divider or logic
level shifter between every ECHO output and GPIO24/GPIO27/GPIO5. Do not connect
a 5 V ECHO pin directly to the Pi.

## Installation on the Raspberry Pi

These steps target Raspberry Pi OS with the camera enabled.

### 1. Enable and test the camera

Use the Raspberry Pi configuration tool to enable the camera interface, reboot,
then confirm the camera works using the Pi OS camera tools before running this
project.

### 2. Install OS-level packages

Picamera2 and the GPIO/camera stack are installed by Raspberry Pi OS, not npm.
Audio uses `espeak` and `aplay` through the 3.5 mm jack.

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-rpi.gpio python3-opencv \
  espeak alsa-utils python3-venv python3-pip
```

### 3. Copy the project and create a virtual environment

Because Picamera2 is installed by Raspberry Pi OS, use
`--system-site-packages` so the virtual environment can see it.

```bash
cd ~/SmartStick
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 diagnose.py
```

This remains a normal Python `venv` plus `pip install -r requirements.txt`
setup. `diagnose.py` must report `READY` before the first hardware run. There
is no JavaScript tooling.

### Copy-to-Pi deployment checklist

Copy the complete project folder, including `models/README.md`, to the Pi. Then
install the OS packages above, create the `--system-site-packages` virtual
environment, run `pip install -r requirements.txt`, copy both model files into
`models/`, and run `python3 diagnose.py`. Only then run `main.py`.

So the honest answer is: **copying the folder plus only `pip install` is not
enough**. The Pi OS camera/GPIO/audio packages and the two model files are also
required. The checklist makes those requirements explicit and repeatable.

### 4. Add the model files

Place these exact pretrained Caffe MobileNet SSD files in `models/`:

```text
models/MobileNetSSD_deploy.prototxt
models/MobileNetSSD_deploy.caffemodel
```

They are intentionally not included in this folder. Verify that both filenames
match exactly; `vision.py` stops with a clear error if either is missing.

### 5. Choose the 3.5 mm headphone output

Configure Raspberry Pi OS audio output to the headphone jack, then test:

```bash
speaker-test -t wav -c 2
espeak "SmartStick audio test"
```

### 6. Run SmartStick

```bash
source venv/bin/activate
python3 main.py --floor-distance 82
```

Open `http://<YOUR_PI_IP_ADDRESS>:5000` from a phone or computer on the same
Wi-Fi network. For example: `http://192.168.1.50:5000`.

Stop with `Ctrl+C`. The program releases GPIO pins and stops the camera.

## Calibration

`--floor-distance` is the normal, flat-floor distance in centimetres from the
downward sensor at its final mounted position. Measure it with the cane held at
normal walking height.

Example for an 84 cm normal floor distance:

```bash
python3 main.py --floor-distance 84
```

The current stair tolerance is ±12 cm in `sensors.py`:

```text
down distance > normal + 12 cm  → downward stair/drop
down distance < normal - 12 cm  → upward stair
otherwise                       → normal floor
```

Calibrate in the real mounting position, then carefully test flat ground,
upward steps, and downward steps. If motion or surface texture creates false
warnings, adjust `stair_change_cm` in `SensorManager` gradually—do not disable
the check without controlled testing.

## Architecture

```text
Three ultrasonic sensors ─┐
                           ├─> sensors.py ──> SensorSnapshot ─┐
Pi Camera + MobileNet SSD ─┘                                  │
                                                               ├─> alerts.py ─> espeak + aplay
Pi Camera + MobileNet SSD ─> vision.py ─> VisionSnapshot ─────┘
                                       └─> annotated JPEG ─> web.py ─> /video
SensorSnapshot + VisionSnapshot ───────────────────────> web.py ─> /sensors
index.html <────────────────────────────────────────────────────── / and JSON
```

`main.py` is the composition root: it starts the sensor loop, vision worker,
alert worker, and Flask server. Modules do one job each. This is deliberate
separation of concerns, not a web-framework-heavy architecture.

## Alert policy

The alert engine evaluates conditions from top to bottom and returns as soon as
it finds one. Therefore only one message is chosen. The audio process and a
three-second cooldown stop overlapping/repeating speech.

| Priority | Condition | Spoken message |
|---:|---|---|
| 1 | Down sensor sees a drop | “Downward stairs ahead” |
| 2 | Down sensor sees raised floor | “Upward stairs ahead” |
| 3 | AI detects person | “Person ahead” |
| 4 | AI detects chair | “Chair ahead” |
| 5 | Left/right ultrasonic obstacle | Side-specific obstacle message |

Because the stair rules return first, side obstacle warnings are suppressed when
stairs are detected. That avoids conflicting instructions at the most critical
moment.

## Optional systemd auto-start

After manual testing is successful, create a service file:

```bash
sudo nano /etc/systemd/system/smartstick.service
```

Use this content, replacing `YOUR_USER` and the paths if your folder differs:

```ini
[Unit]
Description=SmartStick assistive navigation service
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/SmartStick
ExecStart=/home/YOUR_USER/SmartStick/venv/bin/python /home/YOUR_USER/SmartStick/main.py --floor-distance 82
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smartstick.service
sudo systemctl status smartstick.service
```

Useful logs:

```bash
journalctl -u smartstick.service -f
```

## Public project link and cloud deployment

See [DEPLOYMENT.md](DEPLOYMENT.md). The real application is an edge application
that must run on the Pi. Render and similar cloud hosts cannot access its GPIO,
camera, or headphone output, so GitHub is the right public project link until a
separate, clearly labelled simulation or authenticated remote-monitoring system
is built.

## 30-second interview answer

> “SmartStick is a Raspberry Pi 4 assistive-navigation cane prototype. I used
> three ultrasonic sensors for left, right, and floor-distance sensing, and a
> Pi Camera with a pretrained MobileNet SSD model to detect people and chairs.
> A priority-based alert engine converts simultaneous signals into one spoken
> warning, with drop detection taking priority. The system is modular: sensor,
> vision, alert, and Flask monitoring code are separated, while `main.py`
> coordinates their background threads and clean shutdown.”

## Likely interview questions

**Why use ultrasonic sensors and a camera?**

Ultrasonic sensing is cheap, fast, and works without AI for close-range
distance and drops. The camera adds semantic information such as “person” or
“chair.” Combining them covers different limitations.

**Is the stair detector machine learning?**

No. It compares the down-facing sensor distance against a calibrated normal
floor distance. A significant increase means a drop; a decrease means raised
ground.

**What is sensor fusion here?**

It is rule-based fusion: ultrasonic flags and vision flags are combined in one
priority function to decide the single most important alert. It is not a neural
network that merges sensor data.

**How do you prevent conflicting audio?**

`choose_message()` returns only the first matching condition in an explicit
danger order. `speak_if_allowed()` also blocks overlap while `aplay` is running
and uses a cooldown.

**Why threads?**

Hardware reads, vision inference, audio selection, and browser requests take
time. Background workers let these jobs continue independently so the web page
does not freeze sensor safety logic.

**What are the limitations?**

Ultrasonic readings can be affected by angle/soft surfaces, the camera model
can miss or misclassify objects, and Pi 4 inference speed is limited. This is
why calibration, confidence thresholds, timeouts, controlled testing, and an
explicit prototype safety warning matter.

**What would you improve next?**

I would add filtered/multiple sensor samples, object distance estimation,
battery monitoring, a GPS source for mapping, structured event logging, and
field testing with accessibility feedback. A Mapbox map requires GPS hardware
or a phone location source; it is intentionally outside this core version.

## References used by the implementation

- [Raspberry Pi Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
- [OpenCV DNN documentation](https://docs.opencv.org/master/d5/de7/tutorial_dnn_googlenet.html)
- [Flask streaming documentation](https://flask.palletsprojects.com/en/stable/patterns/streaming/)
- [RPi.GPIO basic usage documentation](https://sourceforge.net/p/raspberry-gpio-python/wiki/BasicUsage/)
- [MDN Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)

## Final interview notes

Say what you personally understand and improved: the modular structure,
calibration process, safety-priority rule, and documented startup process. Be
honest that MobileNet SSD is pretrained and that some library-call patterns are
based on their official documentation. That is normal engineering practice.
