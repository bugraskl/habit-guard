# Bundled models: licences and provenance

Habit Guard ships three model files. They run entirely inside OpenCV (`cv2.dnn`
and `cv2.FaceDetectorYN`); no other inference runtime is used and nothing is
downloaded at run time. `scripts/fetch_models.py` recreates and verifies every
model file from the upstream sources below (`--check` verifies without network
access), and `habit_guard.vision.manifest` pins the same checksums.

| File | Size (bytes) | SHA-256 | Licence |
| --- | ---: | --- | --- |
| `face_detection_yunet_2023mar.onnx` | 232 589 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | MIT |
| `palm_detection_mediapipe_2023feb.onnx` | 3 905 734 | `78ff51c38496b7fc8b8ebdb6cc8c1abb02fa6c38427c6848254cdaba57fcce7c` | Apache-2.0 |
| `handpose_estimation_mediapipe_2023feb.onnx` | 4 099 621 | `db0898ae717b76b075d9bf563af315b29562e11f8df5027a1ef07b02bef6d81c` | Apache-2.0 |

The licence texts ship with the models, in the `licenses` folder next to this
file. They cover only these model files; Habit Guard itself is under its own
licence (`LICENSE` in the source tree).

| Licence text | Covers |
| --- | --- |
| [`licenses/LICENSE-APACHE-2.0.txt`](licenses/LICENSE-APACHE-2.0.txt) | the two MediaPipe hand models |
| [`licenses/LICENSE-YUNET.txt`](licenses/LICENSE-YUNET.txt) | the YuNet face detector |

## MediaPipe palm detector and hand landmarks (Apache-2.0)

Copyright Google LLC. Licensed under the Apache License, Version 2.0; a copy of
the licence is in [`licenses/LICENSE-APACHE-2.0.txt`](licenses/LICENSE-APACHE-2.0.txt)
(also at <https://www.apache.org/licenses/LICENSE-2.0>). Model documentation:
<https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker>.

The two files are MediaPipe's palm detection and hand landmark networks,
converted from TFLite to ONNX and simplified by the OpenCV Zoo contributors
(also Apache-2.0), unmodified by Habit Guard:

- Upstream: <https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/palm_detection_mediapipe>
  and <https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/handpose_estimation_mediapipe>
- Pinned commit of the OpenCV Zoo: `47534e27c9851bb1128ccc0102f1145e27f23f98`

The MediaPipe *runtime* (the `mediapipe` Python package) is deliberately not
used: it contains a usage-logging client that uploads to Google servers. Only
the model weights are redistributed; the pre- and post-processing around them
(SSD anchors, box decoding, rotated crops) is Habit Guard's own code in
`habit_guard/vision/hands.py`, following the OpenCV Zoo's reference
implementation and MediaPipe's documented pipeline.

## YuNet face detector (MIT)

From the OpenCV Zoo, originally trained in libfacedetection.train by Shiqi Yu
and contributors. Copyright (c) 2020 Shiqi Yu <shiqi.yu@gmail.com>. Licensed
under the MIT License; the copyright and permission notice are in
[`licenses/LICENSE-YUNET.txt`](licenses/LICENSE-YUNET.txt) (upstream:
<https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE>).

- Upstream: <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>
