<!--
Purpose: Explain safe deployment and public showcase choices for SmartStick.
Interview Explanation: "I distinguished edge deployment from cloud deployment:
the Pi runs hardware, while GitHub documents the project publicly."
Key Concepts: edge computing, systemd, cloud limitations, repository hygiene.
Important Things to Remember: Render cannot access a Pi Camera, GPIO pins, or
the 3.5 mm jack, so it cannot host the real SmartStick service.
Dependencies: GitHub for sharing; Raspberry Pi OS/systemd for real deployment.
Why This File Exists: Prevents an unsafe or misleading cloud deployment claim.
Depends On: README.md setup. Depended On By: project maintainers and recruiters.
Source: Project deployment guidance; no third-party deployment code is included.
-->

# Deployment and public showcase

## Where the real application runs

The real SmartStick application runs **on the Raspberry Pi**, not Render,
Vercel, GitHub Pages, or another normal cloud host. It needs physical GPIO pins,
the Pi Camera, and Pi audio hardware. Use the `systemd` service in `README.md`
after manual Pi testing succeeds.

Do not expose Flask's built-in development server directly to the public
internet. Keep it on your trusted local Wi-Fi during development. A future
remote dashboard should use authentication, HTTPS, and a carefully configured
secure tunnel or VPN; that is a separate security project, not enabled here.

## Best public link for your resume now

1. Create a GitHub repository from this `VisionAi` folder.
2. Keep `models/*.caffemodel` and `models/*.prototxt` out of Git; `.gitignore`
   already does this.
3. Include `README.md`, `LEARNING_GUIDE.md`, and this file.
4. Add real photos/video after Pi testing: sensor wiring, dashboard, and a
   controlled obstacle/stair demonstration.
5. Put the GitHub repository URL on LinkedIn and your resume.

This is stronger and more honest than a cloud URL that cannot operate the
hardware. You can write: “Raspberry Pi edge application with a local Flask
monitoring dashboard.”

## Before marking it as tested

```bash
python3 diagnose.py
python3 main.py --floor-distance 82
```

Only say it is hardware-tested after you perform controlled Pi tests. Until
then, describe it as an implemented prototype awaiting hardware validation.

<!-- INTERVIEW NOTES: Edge computing means computation close to sensors. Here,
the Pi makes safety decisions locally, avoiding dependence on cloud latency. -->
