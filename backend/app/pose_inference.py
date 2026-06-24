from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import onnxruntime as ort

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "best.onnx"
_SESSION: ort.InferenceSession | None = None
_INPUT_NAME: str | None = None


def _load_session() -> Tuple[ort.InferenceSession, str]:
    global _SESSION, _INPUT_NAME
    if _SESSION is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"ONNX model not found: {MODEL_PATH}")
        _SESSION = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
        _INPUT_NAME = _SESSION.get_inputs()[0].name
    return _SESSION, _INPUT_NAME


def _decode_base64_image(image_base64: str) -> np.ndarray:
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[1]
    image_base64 = re.sub(r"\s+", "", image_base64)
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as exc:
        raise ValueError("图像解码失败，请确认上传的是合法的 Base64 编码图像") from exc

    data = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法解码上传的图像，请确认图像格式是否正确")
    return image


def _letterbox(image: np.ndarray, target_shape=(640, 640), color=(114, 114, 114)):
    height, width = image.shape[:2]
    ratio = min(target_shape[0] / height, target_shape[1] / width)
    new_width, new_height = int(round(width * ratio)), int(round(height * ratio))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    dw, dh = target_shape[1] - new_width, target_shape[0] - new_height
    top = int(round(dh / 2 - 0.1))
    bottom = int(round(dh / 2 + 0.1))
    left = int(round(dw / 2 - 0.1))
    right = int(round(dw / 2 + 0.1))
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return padded, ratio, (left, top)


def _preprocess(image: np.ndarray, target_size=(640, 640)) -> tuple[np.ndarray, float, tuple[int, int], tuple[int, int]]:
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    letterboxed, ratio, pad = _letterbox(image_rgb, target_shape=target_size)
    tensor = letterboxed.astype(np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)[None, ...]
    return tensor, ratio, pad, image.shape[:2]


def _postprocess_pose_output(
    output: np.ndarray,
    ratio: float,
    pad: tuple[int, int],
    original_shape: tuple[int, int],
    conf_threshold: float = 0.0,
) -> tuple[list[list[float]], list[float]]:
    if output.ndim != 3 or output.shape[2] < 6 + 17 * 3:
        raise ValueError("模型输出格式不符合预期，请确认 best.onnx 是否为 17 点姿态模型")

    detections = output[0]
    scores = []
    for row in detections:
        obj_conf = float(row[4])
        class_conf = float(row[5]) if row.shape[0] > 6 else 1.0
        if class_conf <= 0.0:
            score = obj_conf
        else:
            score = obj_conf * class_conf
        scores.append(score)

    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])
    if best_score < conf_threshold:
        return [], []

    row = detections[best_index]
    keypoint_data = row[6:]
    if keypoint_data.size != 17 * 3:
        raise ValueError("模型关键点输出维度异常，请检查模型配置")

    original_height, original_width = original_shape
    keypoints: list[list[float]] = []
    visibility: list[float] = []
    for idx in range(17):
        x = float(keypoint_data[idx * 3 + 0])
        y = float(keypoint_data[idx * 3 + 1])
        score = float(keypoint_data[idx * 3 + 2])
        x = (x - pad[0]) / ratio
        y = (y - pad[1]) / ratio
        x /= max(original_width, 1)
        y /= max(original_height, 1)
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        keypoints.append([x, y, score])
        visibility.append(score)

    return keypoints, visibility


def infer_pose_from_image_base64(image_base64: str, conf_threshold: float = 0.2) -> tuple[list[list[float]], list[float]]:
    image = _decode_base64_image(image_base64)
    tensor, ratio, pad, original_shape = _preprocess(image)
    session, input_name = _load_session()
    outputs = session.run(None, {input_name: tensor})
    return _postprocess_pose_output(outputs[0], ratio, pad, original_shape, conf_threshold)
