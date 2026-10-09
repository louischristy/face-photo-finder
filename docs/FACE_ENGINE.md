# Face engine

Face Photo Finder uses a replaceable local face-engine interface. The initial backend is OpenCV DNN with:

- **YuNet** for face detection and five facial landmarks.
- **SFace** for aligned face embeddings and cosine-similarity matching.

The upstream OpenCV Zoo YuNet directory states that its files are MIT licensed. The upstream SFace directory states that its files are Apache-2.0 licensed. OpenCV Zoo itself is Apache-2.0 and explicitly directs users to each model's license. Preserve the relevant license/notice files when model binaries are distributed with a packaged application.

## Privacy

Inference runs on the computer hosting Face Photo Finder. Face embeddings are stored in the project's local index. Search/reference photos are intended to be processed temporarily and deleted after their embeddings are produced.

## Matching semantics

Similarity scores are ranking signals, not identity probabilities. The UI must not label an unknown person by name automatically. Results should use configurable Strict, Balanced and Broad similarity modes and allow human confirmation of candidate groups.

## Models

Model binaries are intentionally excluded from Git. The packaging/model setup process will obtain or bundle the approved upstream ONNX files and retain their license notices.
