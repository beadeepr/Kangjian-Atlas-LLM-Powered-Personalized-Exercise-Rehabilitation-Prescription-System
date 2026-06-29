"""DeepRehabPile 模型评分模块。

通过帧缓冲区将实时的 COCO 17 关键点流组织为固定长度的时间序列，
调用已训练的 Keras 分类/回归模型进行动作质量评分。
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

# ---------- 支持回归的动作（KIMORE 数据集，输出连续分数） ----------
REGRESSION_ACTIONS: set[str] = {
    "lifting_of_arms",  # 抬臂 — KIMORE，同时有分类+回归模型
}

# ---------- 仅支持分类的动作（IRDS 数据集，输出类别） ----------
CLASSIFICATION_ACTIONS: set[str] = {
    "shoulder_abduction_left",    # 左肩外展
    "shoulder_abduction_right",   # 右肩外展
    "shoulder_flexion_left",      # 左肩屈曲
    "shoulder_flexion_right",     # 右肩屈曲
    "shoulder_forward_elevation", # 肩前屈
    "elbow_flexion_left",         # 左肘屈曲
    "elbow_flexion_right",        # 右肘屈曲
}

ML_ACTIONS: set[str] = REGRESSION_ACTIONS | CLASSIFICATION_ACTIONS

# COCO17 → MediaPipe33 映射（来自 pose_runtime.py，此处复用反转方向）
COCO17_TO_MP33 = {
    0: 0, 1: 2, 2: 5, 3: 7, 4: 8,
    5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 10: 16,
    11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 28,
}
MP33_TO_COCO17: dict[int, int] = {v: k for k, v in COCO17_TO_MP33.items()}

# DeepRehabPile 模型固定参数
TARGET_LENGTH: int = 300       # 统一序列帧数
N_JOINTS: int = 17             # COCO 关键点数
N_DIM: int = 2                 # 仅使用 (x, y)
N_CHANNELS: int = N_JOINTS * N_DIM  # 34

# 模型文件路径
MODEL_DIR: Path = Path(__file__).resolve().parents[2] / "models"
CLF_MODEL_PATH: Path = MODEL_DIR / "best_classification_model.keras"
REG_MODEL_PATH: Path = MODEL_DIR / "best_regession_model.keras"  # 保留原始拼写


# ============================================================================
# 评分规则
# ============================================================================

def _map_regression_score(raw: float) -> int:
    """回归模型预测分数映射：百分制 × 10 的倍数。

    Parameters
    ----------
    raw: float
        模型原始输出，[0, 1] 范围归一化值。
    """
    score = int(raw * 100)
    score = max(0, min(100, score))
    return (score // 10) * 10  # 取 10 的倍数（向下取整）


def _map_classification_score(class_id: int) -> int:
    """分类模型预测类别映射（IRDS 数据集标签 [1, 2]）。
    
    模型 softmax 输出索引与原始标签对应关系：
    - 索引 0 → IRDS 标签 1（标准/正确） → 90 分
    - 索引 1 → IRDS 标签 2（不标准/偏差） → 50 分
    """
    return 90 if class_id == 0 else 50


def _build_feedback(action_id: str, score: int, is_regression: bool) -> list[str]:
    """根据分数生成中文反馈消息。"""
    feedback_key = _action_feedback_key(action_id)
    if is_regression:
        if score >= 80:
            return [f"{feedback_key}动作标准，继续保持！"]
        elif score >= 60:
            return [f"{feedback_key}动作基本到位，注意幅度和节奏。"]
        elif score >= 40:
            return [f"{feedback_key}还需改进，请放慢速度、增大活动范围。"]
        else:
            return [f"{feedback_key}偏差较大，请参照标准动作重新练习。"]
    else:
        if score >= 90:
            return [f"{feedback_key}动作标准！"]
        else:
            return [f"{feedback_key}不够标准，请检查姿势并重试。"]


def _action_feedback_key(action_id: str) -> str:
    return {
        "lifting_of_arms": "抬臂",
        "shoulder_abduction_left": "左肩外展",
        "shoulder_abduction_right": "右肩外展",
        "shoulder_flexion_left": "左肩屈曲",
        "shoulder_flexion_right": "右肩屈曲",
        "shoulder_forward_elevation": "肩前屈",
        "elbow_flexion_left": "左肘屈曲",
        "elbow_flexion_right": "右肘屈曲",
    }.get(action_id, "")


# ============================================================================
# DeepRehabScorer
# ============================================================================

class DeepRehabScorer:
    """DeepRehabPile 评分器（单例，线程安全）。

    维护每个 ML 动作的帧缓冲区，周期性地将缓冲的骨架序列送入
    Keras 模型进行推理，并缓存最新评分结果。
    """

    _instance: DeepRehabScorer | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> DeepRehabScorer:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._initialized = False
                    cls._instance = obj
        return cls._instance

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        if self._initialized:
            return

        self._clf_model: Any = None
        self._reg_model: Any = None
        self._model_loaded: bool = False
        self._model_error: str | None = None

        # 帧缓冲区: action_id → deque of (17, 2) float32 arrays
        self._buffers: dict[str, deque[np.ndarray]] = {}

        # 评分缓存: action_id → (score, feedback, timestamp)
        self._cached: dict[str, tuple[int, list[str], float]] = {}

        # 推理间隔（帧数）：每 30 帧触发一次模型推理
        self._inference_interval: int = 30

        self._buffer_lock: threading.Lock = threading.Lock()
        self._initialized = True

        self._load_models()

    # ------------------------------------------------------------------
    # 模型加载
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        """延迟加载 Keras 模型。若加载失败，标记错误并在后续调用时报告。"""
        try:
            import tensorflow as tf

            tf.get_logger().setLevel("ERROR")

            if CLF_MODEL_PATH.exists():
                self._clf_model = tf.keras.models.load_model(
                    str(CLF_MODEL_PATH), compile=False
                )
            if REG_MODEL_PATH.exists():
                self._reg_model = tf.keras.models.load_model(
                    str(REG_MODEL_PATH), compile=False
                )

            self._model_loaded = True
        except Exception as exc:
            self._model_error = str(exc)

    @property
    def is_ready(self) -> bool:
        return self._model_loaded and self._clf_model is not None

    # ------------------------------------------------------------------
    # 关键点提取
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_coco17(keypoints_mp33: list[list[float]]) -> np.ndarray:
        """从 MediaPipe 33 点格式中提取 COCO 17 关键点的 (x, y)。

        Parameters
        ----------
        keypoints_mp33: list[list[float]]
            MediaPipe 33 格式关键点列表。

        Returns
        -------
        np.ndarray, shape (17, 2)
        """
        coco = np.zeros((N_JOINTS, N_DIM), dtype=np.float32)
        for mp_idx, coco_idx in MP33_TO_COCO17.items():
            if mp_idx < len(keypoints_mp33):
                pt = keypoints_mp33[mp_idx]
                coco[coco_idx, 0] = float(pt[0])
                coco[coco_idx, 1] = float(pt[1])
        return coco

    # ------------------------------------------------------------------
    # 帧缓冲
    # ------------------------------------------------------------------

    def buffer_frame(self, action_id: str, keypoints_mp33: list[list[float]]) -> bool:
        """将一帧姿态数据加入指定动作的缓冲区。

        当缓冲区达到 300 帧（完整序列），或每 accumulation_interval 帧时，
        自动触发一次模型推理。

        Returns
        -------
        bool
            True 表示该帧触发了模型推理。
        """
        if not self.is_ready:
            return False
        if action_id not in ML_ACTIONS:
            return False

        with self._buffer_lock:
            if action_id not in self._buffers:
                self._buffers[action_id] = deque(maxlen=TARGET_LENGTH)

            coco = self._extract_coco17(keypoints_mp33)
            self._buffers[action_id].append(coco)
            buf_len = len(self._buffers[action_id])

        # 触发条件：缓冲区满 或 满足采样间隔
        if buf_len == TARGET_LENGTH or (buf_len >= self._inference_interval and buf_len % self._inference_interval == 0):
            self._run_inference(action_id)
            return True
        return False

    # ------------------------------------------------------------------
    # 模型推理
    # ------------------------------------------------------------------

    def _run_inference(self, action_id: str) -> None:
        with self._buffer_lock:
            frames = list(self._buffers[action_id])

        if not frames:
            return

        tensor = self._build_tensor(frames)
        is_reg = action_id in REGRESSION_ACTIONS

        try:
            if is_reg and self._reg_model is not None:
                raw = self._reg_model.predict(tensor, verbose=0)[0][0]
                score = _map_regression_score(float(raw))
            elif self._clf_model is not None:
                logits = self._clf_model.predict(tensor, verbose=0)[0]
                class_id = int(np.argmax(logits))
                score = _map_classification_score(class_id)
            else:
                return
        except Exception:
            return

        feedback = _build_feedback(action_id, score, is_reg)

        with self._buffer_lock:
            self._cached[action_id] = (score, feedback, time.time())

    def _build_tensor(self, frames: list[np.ndarray]) -> np.ndarray:
        """将帧缓冲区构建为模型输入张量。

        Parameters
        ----------
        frames: list of (17, 2) arrays

        Returns
        -------
        np.ndarray, shape (1, 300, 34)
        """
        raw = len(frames)

        if raw < TARGET_LENGTH:
            # 重复最后一帧补齐
            pad_count = TARGET_LENGTH - raw
            frames = frames + [frames[-1]] * pad_count
        else:
            # 取最后 300 帧
            frames = frames[-TARGET_LENGTH:]

        arr = np.array(frames, dtype=np.float32)  # (300, 17, 2)

        # Min-Max 归一化（逐通道，防止除零）
        flat = arr.reshape(TARGET_LENGTH, N_CHANNELS)  # (300, 34)
        min_vals = flat.min(axis=0, keepdims=True)
        max_vals = flat.max(axis=0, keepdims=True)
        denom = max_vals - min_vals
        denom[denom == 0] = 1.0
        flat = (flat - min_vals) / denom

        return flat[np.newaxis, :, :]  # (1, 300, 34)

    # ------------------------------------------------------------------
    # 结果查询
    # ------------------------------------------------------------------

    def get_cached_score(self, action_id: str) -> int | None:
        with self._buffer_lock:
            entry = self._cached.get(action_id)
        if entry is None:
            return None
        return entry[0]

    def get_cached_feedback(self, action_id: str) -> list[str] | None:
        with self._buffer_lock:
            entry = self._cached.get(action_id)
        if entry is None:
            return None
        return entry[1]

    def get_result(self, action_id: str) -> dict[str, Any] | None:
        """返回完整的评分结果（用于 Checker 集成）。"""
        score = self.get_cached_score(action_id)
        if score is None:
            return None
        feedback = self.get_cached_feedback(action_id) or []
        status = "ok" if score >= 80 else "warning" if score >= 45 else "error"
        return {"feedback": feedback, "score": score, "status": status}

    # ------------------------------------------------------------------
    # 缓冲区管理
    # ------------------------------------------------------------------

    def reset_action(self, action_id: str) -> None:
        """重置指定动作的缓冲区和缓存。"""
        with self._buffer_lock:
            self._buffers.pop(action_id, None)
            self._cached.pop(action_id, None)

    def buffer_size(self, action_id: str) -> int:
        with self._buffer_lock:
            buf = self._buffers.get(action_id)
        return len(buf) if buf else 0


# ============================================================================
# 全局单例
# ============================================================================

_scorer: DeepRehabScorer | None = None


def get_scorer() -> DeepRehabScorer:
    global _scorer
    if _scorer is None:
        _scorer = DeepRehabScorer()
    return _scorer
