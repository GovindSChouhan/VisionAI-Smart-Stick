<!--
Purpose: Document the externally supplied Caffe model files required by vision.py.
Interview Explanation: "The model is a pretrained deployment asset, separated
from source code because it is large and has its own licensing/source history."
Key Concepts: Caffe architecture file, trained weights, versioned artifacts.
Important Things to Remember: Both exact filenames are required and are not in
Git by default. Do not rename them unless you update vision.py.
Dependencies: vision.py and diagnose.py look in this directory.
Why This File Exists: Prevents a missing-model startup failure after copying.
Depends On: Nothing. Depended On By: developers preparing a Pi deployment.
Source: The project does not claim authorship of MobileNet SSD; use the trusted
source from which your existing model files were obtained and retain its licence.
-->

# Required model files

Copy these two files into this folder before running SmartStick:

```text
MobileNetSSD_deploy.prototxt
MobileNetSSD_deploy.caffemodel
```

`vision.py` uses OpenCV's Caffe loader. The `.prototxt` file describes the
network architecture; the `.caffemodel` file contains pretrained weights. They
must have the exact filenames above.

Run `python3 diagnose.py` on the Pi to confirm they are present.

<!-- INTERVIEW NOTES: I used a pretrained model for inference; I did not claim
to train it. The application detects only the `person` and `chair` classes. -->
