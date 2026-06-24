from __future__ import annotations

import asyncio
import base64
import binascii
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .algorithms import analyze_pose
from .spatial import build_ar_overlay, build_skeleton_frame
from .voice_feedback import build_voice_cue


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "best.onnx"
COCO17_TO_MEDIAPIPE33 = {
    0: 0,
    1: 2,
    2: 5,
    3: 7,
    4: 8,
    5: 11,
    6: 12,
    7: 13,
    8: 14,
    9: 15,
    10: 16,
    11: 23,
    12: 24,
    13: 25,
    14: 26,
    15: 27,
    16: 28,
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _decode_base64_image(image_base64: str) -> np.ndarray:
    try:
        data = base64.b64decode(image_base64.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image_base64 is invalid") from exc
    if not data:
        raise ValueError("image_base64 is empty")
    try:
        import cv2
    except Exception as exc:
        raise RuntimeError("opencv-python is required for server-side frame decoding") from exc
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image_base64 is not a supported image")
    return image


def _softmax(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    values = values - np.max(values)
    exp = np.exp(values)
    total = np.sum(exp)
    return exp / total if total else exp


@dataclass
class PoseRuntimeStatus:
    provider: str
    model_path: str
    model_loaded: bool
    mode: str
    input_name: str | None = None
    input_shape: list[Any] | None = None
    output_names: list[str] = field(default_factory=list)
    error: str | None = None


class RTMPoseRuntime:
    def __init__(self):
        self.model_path = Path(os.getenv("RTMPOSE_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
        self.input_size = self._parse_input_size(os.getenv("RTMPOSE_INPUT_SIZE", "256,192"))
        self.providers = self._parse_providers(os.getenv("RTMPOSE_PROVIDERS", "CPUExecutionProvider"))
        self.session = None
        self.input_name = None
        self.input_shape = None
        self.output_names: list[str] = []
        self.error = None
        self._load()

    def _parse_input_size(self, raw: str) -> tuple[int, int]:
        try:
            height, width = [int(part.strip()) for part in raw.split(",", 1)]
            return max(32, height), max(32, width)
        except Exception:
            return 256, 192

    def _parse_providers(self, raw: str) -> list[str]:
        providers = [item.strip() for item in raw.split(",") if item.strip()]
        return providers or ["CPUExecutionProvider"]

    def _load(self):
        if not self.model_path.exists():
            self.error = f"model not found: {self.model_path}"
            return
        try:
            import onnxruntime as ort

            available = set(ort.get_available_providers())
            providers = [provider for provider in self.providers if provider in available]
            if not providers:
                providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            model_input = self.session.get_inputs()[0]
            self.input_name = model_input.name
            self.input_shape = list(model_input.shape)
            self.output_names = [output.name for output in self.session.get_outputs()]
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            self.session = None

    def status(self) -> PoseRuntimeStatus:
        return PoseRuntimeStatus(
            provider="rtmpose-onnx",
            model_path=str(self.model_path.relative_to(BASE_DIR)) if self.model_path.is_relative_to(BASE_DIR) else str(self.model_path),
            model_loaded=self.session is not None,
            mode="onnx" if self.session is not None else "keypoint_passthrough",
            input_name=self.input_name,
            input_shape=self.input_shape,
            output_names=self.output_names,
            error=self.error,
        )

    def infer_image(self, image_base64: str) -> dict[str, Any]:
        started = time.perf_counter()
        if self.session is None:
            raise RuntimeError(self.error or "RTMPose ONNX session is not available")
        image = _decode_base64_image(image_base64)
        tensor, scale = self._preprocess(image)
        outputs = self.session.run(self.output_names or None, {self.input_name: tensor})
        keypoints, visibility = self._decode_outputs(outputs, scale)
        return {
            "keypoints": keypoints,
            "visibility": visibility,
            "provider": "rtmpose-onnx",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    def _preprocess(self, image: np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
        try:
            import cv2
        except Exception as exc:
            raise RuntimeError("opencv-python is required for server-side frame preprocessing") from exc
        input_h, input_w = self.input_size
        height, width = image.shape[:2]
        resized = cv2.resize(image, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (rgb - mean) / std
        tensor = normalized.transpose(2, 0, 1)[None, :, :, :].astype(np.float32)
        return tensor, (width / input_w, height / input_h)

    def _decode_outputs(self, outputs: list[np.ndarray], scale: tuple[float, float]) -> tuple[list[list[float]], list[float]]:
        for output in outputs:
            keypoints = self._decode_coordinate_output(output, scale)
            if keypoints:
                return self._to_mediapipe33(keypoints)
        for output in outputs:
            keypoints = self._decode_heatmap_output(output, scale)
            if keypoints:
                return self._to_mediapipe33(keypoints)
        raise RuntimeError("unsupported RTMPose output format")

    def _decode_coordinate_output(self, output: np.ndarray, scale: tuple[float, float]) -> list[list[float]]:
        arr = np.asarray(output)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim != 2 or arr.shape[0] < 1 or arr.shape[1] < 2:
            return []
        if arr.shape[0] > 33 and arr.shape[1] in {17, 26, 33}:
            arr = arr.T
        if arr.shape[0] not in {17, 26, 33}:
            return []
        keypoints = []
        input_h, input_w = self.input_size
        for point in arr:
            x = float(point[0])
            y = float(point[1])
            score = float(point[2]) if len(point) > 2 else 1.0
            if x > 2 or y > 2:
                x = x / input_w
                y = y / input_h
            keypoints.append([max(0.0, min(1.0, x)), max(0.0, min(1.0, y)), 0.0, max(0.0, min(1.0, score))])
        return keypoints

    def _decode_heatmap_output(self, output: np.ndarray, scale: tuple[float, float]) -> list[list[float]]:
        arr = np.asarray(output)
        if arr.ndim == 4:
            arr = arr[0]
        if arr.ndim != 3:
            return []
        if arr.shape[0] not in {17, 26, 33}:
            return []
        _, heat_h, heat_w = arr.shape
        keypoints = []
        for heatmap in arr:
            flat_index = int(np.argmax(heatmap))
            y, x = divmod(flat_index, heat_w)
            prob = _softmax(heatmap.reshape(-1))[flat_index]
            keypoints.append([x / max(1, heat_w - 1), y / max(1, heat_h - 1), 0.0, float(prob)])
        return keypoints

    def _to_mediapipe33(self, keypoints: list[list[float]]) -> tuple[list[list[float]], list[float]]:
        if len(keypoints) >= 33:
            points = [[point[0], point[1], point[2] if len(point) > 2 else 0.0] for point in keypoints[:33]]
            visibility = [float(point[3]) if len(point) > 3 else 1.0 for point in keypoints[:33]]
            return points, visibility

        points = [[0.0, 0.0, 0.0] for _ in range(33)]
        visibility = [0.0 for _ in range(33)]
        for source_index, target_index in COCO17_TO_MEDIAPIPE33.items():
            if source_index >= len(keypoints):
                continue
            point = keypoints[source_index]
            points[target_index] = [point[0], point[1], point[2] if len(point) > 2 else 0.0]
            visibility[target_index] = float(point[3]) if len(point) > 3 else 1.0
        return points, visibility


runtime = RTMPoseRuntime()


@dataclass
class PoseFrame:
    action_id: str
    frame_id: str
    timestamp: int | None = None
    image_base64: str | None = None
    keypoints: list[list[float]] | None = None
    visibility: list[float] | None = None


@dataclass
class PoseStreamSession:
    session_id: str
    created_at: float = field(default_factory=time.time)
    processed_frames: int = 0
    dropped_frames: int = 0
    last_latency_ms: float | None = None


class PoseStreamManager:
    def __init__(self):
        self.sessions: dict[str, PoseStreamSession] = {}

    def create_session(self) -> PoseStreamSession:
        session = PoseStreamSession(session_id=str(uuid.uuid4()))
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str | None) -> PoseStreamSession:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        return self.create_session()

    def close_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    async def process_frame(self, frame: PoseFrame, session: PoseStreamSession | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        inference = self._resolve_keypoints(frame)
        result = analyze_pose(
            action_id=frame.action_id,
            keypoints=inference["keypoints"],
            visibility=inference["visibility"],
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if session:
            session.processed_frames += 1
            session.last_latency_ms = latency_ms
        return {
            "frame_id": frame.frame_id,
            "timestamp": frame.timestamp or _now_ms(),
            "keypoints": inference["keypoints"],
            "visibility": inference["visibility"],
            "skeleton_3d": build_skeleton_frame(
                inference["keypoints"],
                inference["visibility"],
                action_id=frame.action_id,
            ),
            "ar_overlay": build_ar_overlay(
                frame.action_id,
                inference["keypoints"],
                inference["visibility"],
                feedback=result.get("feedback", []),
                status=result.get("status"),
                score=result.get("score"),
            ),
            "feedback": result.get("feedback", []),
            "score": result.get("score"),
            "status": result.get("status"),
            "voice_cue": build_voice_cue(
                result.get("feedback", []),
                status=result.get("status"),
                score=result.get("score"),
            ),
            "provider": inference["provider"],
            "latency_ms": latency_ms,
            "inference_latency_ms": inference.get("latency_ms"),
        }

    async def process_batch(
        self,
        frames: list[PoseFrame],
        session: PoseStreamSession | None = None,
        max_concurrency: int = 2,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        semaphore = asyncio.Semaphore(max(1, max_concurrency))

        async def run(frame: PoseFrame):
            async with semaphore:
                return await self.process_frame(frame, session=session)

        results = await asyncio.gather(*(run(frame) for frame in frames))
        return {
            "results": results,
            "batch_size": len(frames),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    def _resolve_keypoints(self, frame: PoseFrame) -> dict[str, Any]:
        if frame.keypoints:
            return {
                "keypoints": frame.keypoints,
                "visibility": frame.visibility or [1.0] * len(frame.keypoints),
                "provider": "keypoint_passthrough",
                "latency_ms": 0.0,
            }
        if frame.image_base64:
            return runtime.infer_image(frame.image_base64)
        raise ValueError("keypoints or image_base64 required")


stream_manager = PoseStreamManager()


def pose_runtime_status() -> dict[str, Any]:
    status = runtime.status()
    return {
        "provider": status.provider,
        "model_path": status.model_path,
        "model_loaded": status.model_loaded,
        "mode": status.mode,
        "input_name": status.input_name,
        "input_shape": status.input_shape,
        "output_names": status.output_names,
        "error": status.error,
        "active_sessions": len(stream_manager.sessions),
        "webrtc_available": _webrtc_available(),
    }


def _webrtc_available() -> bool:
    try:
        import aiortc  # noqa: F401

        return True
    except Exception:
        return False
