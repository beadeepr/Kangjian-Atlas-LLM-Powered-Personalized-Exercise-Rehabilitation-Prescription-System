from __future__ import annotations

from typing import Any

import numpy as np

from .deep_rehab_scorer import ML_ACTIONS, get_scorer


COCO_KEYPOINTS = {
    "nose": 0,
    "left_eye": 1,
    "right_eye": 2,
    "left_ear": 3,
    "right_ear": 4,
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_elbow": 7,
    "right_elbow": 8,
    "left_wrist": 9,
    "right_wrist": 10,
    "left_hip": 11,
    "right_hip": 12,
    "left_knee": 13,
    "right_knee": 14,
    "left_ankle": 15,
    "right_ankle": 16,
}


def calculate_angle(a: list[float], b: list[float], c: list[float]) -> float:
    """Calculate the angle formed by three pose points, with b as the vertex."""
    a_arr = np.array(a[:3], dtype=float)
    b_arr = np.array(b[:3], dtype=float)
    c_arr = np.array(c[:3], dtype=float)
    ba = a_arr - b_arr
    bc = c_arr - b_arr
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom == 0:
        return 0.0
    cosine_angle = np.dot(ba, bc) / denom
    return float(np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0))))


def calculate_distance(p1: list[float], p2: list[float]) -> float:
    """Calculate Euclidean distance between two pose points."""
    return float(np.linalg.norm(np.array(p1[:3], dtype=float) - np.array(p2[:3], dtype=float)))


def midpoint(p1: list[float], p2: list[float]) -> list[float]:
    return [(p1[i] + p2[i]) / 2 for i in range(3)]


# ========================================================================
# 连续评分 & 时序平滑 工具函数
# ========================================================================

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    """t in [0, 1]; 返回 a + (b-a)*t"""
    return a + (b - a) * t


def _linear_map(
    value: float,
    best: float,
    worst: float,
    best_score: float = 95.0,
    worst_score: float = 30.0,
) -> float:
    """将测量值线性映射为连续分数。best -> best_score, worst -> worst_score。

    对于「越小越好」的指标 (如距离): best < worst
    对于「越大越好」的指标 (如角度): best > worst
    """
    if abs(worst - best) < 1e-9:
        return best_score
    ratio = _clamp((value - best) / (worst - best), 0.0, 1.0)
    return _lerp(best_score, worst_score, ratio)


def _range_score(
    value: float,
    opt_lo: float,
    opt_hi: float,
    bad_lo: float,
    bad_hi: float,
    max_score: float = 95.0,
    min_score: float = 30.0,
) -> float:
    """区间评分：值在 [opt_lo, opt_hi] 内得 max_score，
    偏离到 [bad_lo, bad_hi] 时线性衰减至 min_score。
    """
    if opt_lo <= value <= opt_hi:
        return max_score
    if value < opt_lo:
        if opt_lo <= bad_lo:
            return min_score
        ratio = _clamp((opt_lo - value) / (opt_lo - bad_lo), 0.0, 1.0)
    else:
        if bad_hi <= opt_hi:
            return min_score
        ratio = _clamp((value - opt_hi) / (bad_hi - opt_hi), 0.0, 1.0)
    return _lerp(max_score, min_score, ratio)


# ---------- 时序平滑 ----------

# {action_id: smoothed_score}
_smooth_state: dict[str, float] = {}
_SMOOTH_ALPHA: float = 0.35  # EMA 系数（约 3 帧收敛）


def _smooth_score(raw_score: float, action_id: str) -> int:
    """对原始评分做 EMA 时序平滑，消除逐帧抖动。"""
    prev = _smooth_state.get(action_id, raw_score)
    smoothed = prev + _SMOOTH_ALPHA * (raw_score - prev)
    _smooth_state[action_id] = smoothed
    return max(0, min(100, int(round(smoothed))))


def reset_smooth_state(action_id: str | None = None) -> None:
    """重置时序平滑状态。action_id 为 None 时全部清除。"""
    global _smooth_state
    if action_id is None:
        _smooth_state.clear()
    else:
        _smooth_state.pop(action_id, None)


# ---------- 评分响应 ----------

def _score_response(feedback: list[str], score: int, *, action_id: str = "") -> dict[str, Any]:
    """生成统一评分响应（含时序平滑与状态判定）。

    Parameters
    ----------
    feedback : 反馈消息列表。
    score : 原始整数分数 [0, 100]。
    action_id : 非空时启用 EMA 平滑。
    """
    score = max(0, min(100, int(score)))
    if action_id:
        score = _smooth_score(float(score), action_id)
    if score >= 80:
        status = "ok"
    elif score >= 45:
        status = "warning"
    else:
        status = "error"
    return {"feedback": feedback, "score": score, "status": status}


def _graded_feedback(
    score: float,
    excellent_msg: str,
    good_msg: str,
    fair_msg: str,
    poor_msg: str,
    *,
    thr_excellent: float = 88.0,
    thr_good: float = 72.0,
    thr_fair: float = 50.0,
) -> list[str]:
    """按分数区间选取分级反馈消息。"""
    if score >= thr_excellent:
        return [excellent_msg]
    if score >= thr_good:
        return [good_msg]
    if score >= thr_fair:
        return [fair_msg]
    return [poor_msg]


# ========================================================================
# 关键点可见性守卫
# ========================================================================

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


def _normalize_to_coco17(
    keypoints: list[list[float]],
    visibility: list[float] | None,
) -> tuple[list[list[float]], list[float]]:
    if not keypoints:
        return keypoints, visibility or []
    if len(keypoints) <= 17:
        vis = visibility or [1.0] * len(keypoints)
        return keypoints, vis

    if len(keypoints) >= 33:
        coco_keypoints: list[list[float]] = []
        coco_visibility: list[float] = []
        for coco_idx in range(17):
            mp_idx = COCO17_TO_MEDIAPIPE33[coco_idx]
            point = keypoints[mp_idx] if mp_idx < len(keypoints) else [0.0, 0.0, 0.0]
            coco_keypoints.append(point)
            if visibility and mp_idx < len(visibility):
                coco_visibility.append(float(visibility[mp_idx]))
            elif len(point) > 3:
                coco_visibility.append(float(point[3]))
            else:
                coco_visibility.append(1.0)
        return coco_keypoints, coco_visibility

    return keypoints, visibility or [1.0] * len(keypoints)


KEYPOINT_NAMES = {
    0: "鼻子",
    1: "左眼",
    2: "右眼",
    3: "左耳",
    4: "右耳",
    5: "左肩",
    6: "右肩",
    7: "左肘",
    8: "右肘",
    9: "左腕",
    10: "右腕",
    11: "左髋",
    12: "右髋",
    13: "左膝",
    14: "右膝",
    15: "左踝",
    16: "右踝",
}


def _visibility_guard(action_id: str, keypoints: list[list[float]], visibility: list[float]) -> dict[str, Any] | None:
    required_map = {
        "neck_chin_tuck": [COCO_KEYPOINTS["nose"], COCO_KEYPOINTS["left_ear"], COCO_KEYPOINTS["right_ear"], COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"]],
        "chin_tuck": [COCO_KEYPOINTS["nose"], COCO_KEYPOINTS["left_ear"], COCO_KEYPOINTS["right_ear"], COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"]],
        "neck_side_bend": [COCO_KEYPOINTS["nose"], COCO_KEYPOINTS["left_ear"], COCO_KEYPOINTS["right_ear"], COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"]],
        "scapular_retraction": [COCO_KEYPOINTS["left_ear"], COCO_KEYPOINTS["right_ear"], COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"]],
        "thoracic_extension": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"]],
        "mckenzie_press_up": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_wrist"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"]],
        "pelvic_tilt": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"]],
        "bird_dog": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"]],
        "dead_bug": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_wrist"]],
        "glute_bridge": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"]],
        "wall_squat": [COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"], COCO_KEYPOINTS["left_ankle"], COCO_KEYPOINTS["right_ankle"]],
        "straight_leg_raise": [COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"], COCO_KEYPOINTS["left_ankle"], COCO_KEYPOINTS["right_ankle"]],
        "quad_set": [COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"], COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"]],
        "calf_stretch": [COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"], COCO_KEYPOINTS["left_ankle"], COCO_KEYPOINTS["right_ankle"]],
        "ankle_pump": [COCO_KEYPOINTS["left_knee"], COCO_KEYPOINTS["right_knee"], COCO_KEYPOINTS["left_ankle"], COCO_KEYPOINTS["right_ankle"]],
        "shoulder_pendulum": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_wrist"]],
        "shoulder_external_rotation": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_hip"], COCO_KEYPOINTS["right_hip"]],
        # ---- ML 动作 ----
        "lifting_of_arms": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_wrist"]],
        "shoulder_abduction_left": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_shoulder"]],
        "shoulder_abduction_right": [COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["right_wrist"], COCO_KEYPOINTS["left_shoulder"]],
        "shoulder_flexion_left": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_shoulder"]],
        "shoulder_flexion_right": [COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["right_wrist"], COCO_KEYPOINTS["left_shoulder"]],
        "shoulder_forward_elevation": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["left_wrist"], COCO_KEYPOINTS["right_wrist"]],
        "elbow_flexion_left": [COCO_KEYPOINTS["left_shoulder"], COCO_KEYPOINTS["left_elbow"], COCO_KEYPOINTS["left_wrist"]],
        "elbow_flexion_right": [COCO_KEYPOINTS["right_shoulder"], COCO_KEYPOINTS["right_elbow"], COCO_KEYPOINTS["right_wrist"]],
    }
    if not visibility:
        return None
    required = required_map.get(action_id, list(range(min(17, len(visibility)))))
    missing = []
    for index in required:
        if index >= len(visibility) or visibility[index] < 0.1:
            missing.append(KEYPOINT_NAMES.get(index, f"关键点{index}"))
    if not missing:
        return None
    if len(missing) == len(required):
        return {
            "feedback": [
                "未识别到该动作的关键关节，请确保目标部位完整入镜并重新采集姿态。",
            ],
            "score": 0,
            "status": "error",
        }
    if len(missing) == 1:
        message = f"未识别到{missing[0]}，请调整摄像头角度或使该部位更清晰可见。"
    else:
        message = f"未识别到{'、'.join(missing[:-1])}和{missing[-1]}，请调整摄像头角度或使这些部位更清晰可见。"
    return {
        "feedback": [message],
        "score": 35,
        "status": "warning",
    }


# ========================================================================
# 核心分析入口
# ========================================================================

def analyze_pose(
    action_id: str,
    keypoints: list[list[float]],
    visibility: list[float],
    *,
    ml_buffered: bool = False,
) -> dict[str, Any]:
    action_id = "neck_chin_tuck" if action_id == "chin_tuck" else action_id
    keypoints, visibility = _normalize_to_coco17(keypoints, visibility)
    if action_id in ML_ACTIONS and not ml_buffered:
        get_scorer().buffer_frame_coco17(action_id, keypoints)
    if result := _visibility_guard(action_id, keypoints, visibility):
        return result

    checkers = {
        "neck_chin_tuck": _check_neck_chin_tuck,
        "neck_side_bend": _check_neck_bend,
        "scapular_retraction": _check_scapular_retraction,
        "thoracic_extension": _check_thoracic_extension,
        "mckenzie_press_up": _check_mckenzie_press_up,
        "pelvic_tilt": _check_pelvic_tilt,
        "bird_dog": _check_bird_dog,
        "dead_bug": _check_dead_bug,
        "glute_bridge": _check_glute_bridge,
        "wall_squat": _check_wall_squat,
        "straight_leg_raise": _check_straight_leg_raise,
        "quad_set": _check_quad_set,
        "calf_stretch": _check_calf_stretch,
        "ankle_pump": _check_ankle_pump,
        "shoulder_pendulum": _check_shoulder_pendulum,
        "shoulder_external_rotation": _check_shoulder_external_rotation,
        # ---- ML ----
        "lifting_of_arms": _check_lifting_of_arms,
        "shoulder_abduction_left": _check_shoulder_abduction_left,
        "shoulder_abduction_right": _check_shoulder_abduction_right,
        "shoulder_flexion_left": _check_shoulder_flexion_left,
        "shoulder_flexion_right": _check_shoulder_flexion_right,
        "shoulder_forward_elevation": _check_shoulder_forward_elevation,
        "elbow_flexion_left": _check_elbow_flexion_left,
        "elbow_flexion_right": _check_elbow_flexion_right,
    }
    checker = checkers.get(action_id)
    if not checker:
        return {"feedback": ["该动作暂未配置实时纠正规则，请先按动作说明完成。"], "score": 0, "status": "error"}
    return checker(keypoints)


# ========================================================================
# 16 个算法评分动作 — 连续评分 + 分级反馈
# ========================================================================

# ---- neck_chin_tuck: 下巴回收训练 ----

def _check_neck_chin_tuck(keypoints: list[list[float]]) -> dict[str, Any]:
    """下巴回收：鼻子与耳朵 x 距离越小越好。"""
    nose = keypoints[COCO_KEYPOINTS["nose"]]
    ear_mid = midpoint(keypoints[COCO_KEYPOINTS["left_ear"]], keypoints[COCO_KEYPOINTS["right_ear"]])
    dist = abs(nose[0] - ear_mid[0])

    # 连续评分：0 → 95, 0.06 → 75, 0.15 → 30
    raw = _linear_map(dist, best=0.0, worst=0.15, best_score=95, worst_score=30)

    feedback = _graded_feedback(
        raw,
        "下巴回收到位，头颈竖直，动作非常标准！",
        "下巴回收良好，可再向后收一点让双下巴更明显。",
        '下巴回收不够，请像做\u201c双下巴\u201d一样缓慢向后收。',
        "下巴尚未回收，请从头开始，缓慢将下巴向颈部方向收。",
    )
    return _score_response(feedback, int(round(raw)), action_id="neck_chin_tuck")


# ---- neck_side_bend: 颈部侧屈拉伸 ----

def _check_neck_bend(keypoints: list[list[float]]) -> dict[str, Any]:
    """颈部侧屈：耳朵到同侧肩距离越小越好，同时还检查是否正对摄像头。"""
    left_ear = keypoints[COCO_KEYPOINTS["left_ear"]]
    right_ear = keypoints[COCO_KEYPOINTS["right_ear"]]
    left_shoulder = keypoints[COCO_KEYPOINTS["left_shoulder"]]
    right_shoulder = keypoints[COCO_KEYPOINTS["right_shoulder"]]
    nose = keypoints[COCO_KEYPOINTS["nose"]]

    shoulder_mid_x = (left_shoulder[0] + right_shoulder[0]) / 2
    alignment_ok = abs(nose[0] - shoulder_mid_x) <= 0.09

    dist_left = calculate_distance(left_ear, left_shoulder)
    dist_right = calculate_distance(right_ear, right_shoulder)
    active_dist = min(dist_left, dist_right)

    if not alignment_ok:
        # 未正对摄像头：基于距离给分但封顶 65
        raw = _linear_map(active_dist, best=0.0, worst=0.25, best_score=95, worst_score=25)
        raw = min(raw, 65)
        return _score_response(
            ["请正对摄像头，避免转头或身体旋转，再进行侧屈。"],
            int(round(raw)),
            action_id="neck_side_bend",
        )

    # 连续评分：0 → 95, 0.10 → 80, 0.25 → 25
    raw = _linear_map(active_dist, best=0.0, worst=0.25, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "侧屈幅度很好，颈部拉伸充分，保持呼吸不要耸肩。",
        "侧屈方向正确，再轻一点靠近同侧肩部，感受颈侧拉伸。",
        "请缓慢将耳朵向同侧肩部靠近，幅度还可加大。",
        "请从正中位开始，缓慢侧屈头部，让耳朵靠近肩部。",
    )
    return _score_response(feedback, int(round(raw)), action_id="neck_side_bend")


# ---- scapular_retraction: 肩胛后缩训练 ----

def _check_scapular_retraction(keypoints: list[list[float]]) -> dict[str, Any]:
    """肩胛后缩：耳朵 y 应明显大于肩 y（肩下沉），差值越大越好。"""
    shoulder_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    ear_y = (keypoints[COCO_KEYPOINTS["left_ear"]][1] + keypoints[COCO_KEYPOINTS["right_ear"]][1]) / 2
    gap = ear_y - shoulder_y  # 正值 = 肩低于耳（正确下沉）

    # 连续评分：gap ≥ 0.15 → 95, 0.12 → 78, 0.02 → 30
    raw = _linear_map(gap, best=0.15, worst=0.02, best_score=95, worst_score=30)

    feedback = _graded_feedback(
        raw,
        "肩部下沉到位，肩胛后缩稳定，继续保持。",
        "肩部下沉良好，再向后下方夹紧肩胛骨。",
        "肩部有上提趋势，请先沉肩，再把肩胛骨向后下方夹紧。",
        "肩部明显上提（耸肩），请先放松肩膀下垂，再尝试后缩。",
    )
    return _score_response(feedback, int(round(raw)), action_id="scapular_retraction")


# ---- thoracic_extension: 胸椎伸展训练 ----

def _check_thoracic_extension(keypoints: list[list[float]]) -> dict[str, Any]:
    """胸椎伸展：肩 y 应小于髋 y（上身后仰），差值越负越好。"""
    shoulder_mid = midpoint(keypoints[COCO_KEYPOINTS["left_shoulder"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    hip_mid = midpoint(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    diff = shoulder_mid[1] - hip_mid[1]  # 负值 = 后仰（正确）

    # 连续评分：diff ≤ -0.05 → 95, 0.0 → 72, 0.10 → 25
    raw = _linear_map(diff, best=-0.05, worst=0.10, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "胸椎伸展充分，上身后仰到位，注意不要用腰部代偿。",
        "胸椎伸展良好，可再向后仰一点，感受上背部伸展。",
        "身体略前倾，请坐直并从胸椎段向后伸展。",
        "身体明显前倾，请先挺直腰背，再从胸椎处缓慢后仰。",
    )
    return _score_response(feedback, int(round(raw)), action_id="thoracic_extension")


# ---- mckenzie_press_up: 麦肯基俯卧撑 ----

def _check_mckenzie_press_up(keypoints: list[list[float]]) -> dict[str, Any]:
    """麦肯基俯卧撑：肘关节角度越大越好（手臂充分伸直）。"""
    left_elbow_angle = calculate_angle(
        keypoints[COCO_KEYPOINTS["left_shoulder"]],
        keypoints[COCO_KEYPOINTS["left_elbow"]],
        keypoints[COCO_KEYPOINTS["left_wrist"]],
    )
    right_elbow_angle = calculate_angle(
        keypoints[COCO_KEYPOINTS["right_shoulder"]],
        keypoints[COCO_KEYPOINTS["right_elbow"]],
        keypoints[COCO_KEYPOINTS["right_wrist"]],
    )
    elbow_angle = max(left_elbow_angle, right_elbow_angle)

    # 连续评分：≥ 175° → 95, 155° → 70, 130° → 25
    raw = _linear_map(elbow_angle, best=175.0, worst=130.0, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "手臂充分伸直，胸部抬离地面，骨盆保持贴地，非常标准！",
        "手臂伸展良好，可再用力撑起，让肘关节完全打直。",
        "手臂伸展不够，请用手臂力量撑起上半身，腰部不要出现锐痛。",
        "手臂弯曲较多，请从俯卧位开始，用手臂力量缓慢推起上半身。",
    )
    return _score_response(feedback, int(round(raw)), action_id="mckenzie_press_up")


# ---- pelvic_tilt: 骨盆后倾训练 ----

def _check_pelvic_tilt(keypoints: list[list[float]]) -> dict[str, Any]:
    """骨盆后倾：仰卧位肩与髋 y 坐标应接近，差值越小越好。"""
    shoulder_mid_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    hip_mid_y = (keypoints[COCO_KEYPOINTS["left_hip"]][1] + keypoints[COCO_KEYPOINTS["right_hip"]][1]) / 2
    gap = abs(hip_mid_y - shoulder_mid_y)

    # 连续评分：0.0 → 95, 0.08 → 80, 0.25 → 25
    raw = _linear_map(gap, best=0.0, worst=0.25, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "核心收紧，腰背轻贴地面，骨盆后倾幅度小而稳定！",
        "腹部收紧良好，骨盆后倾方向正确，再轻微收一点。",
        "请保持仰卧屈膝姿势，专注骨盆轻微后倾，让腰部贴地。",
        "身体未保持水平，请先调整至仰卧屈膝位，再尝试骨盆后倾。",
    )
    return _score_response(feedback, int(round(raw)), action_id="pelvic_tilt")


# ---- bird_dog: 鸟狗式核心训练 ----

def _check_bird_dog(keypoints: list[list[float]]) -> dict[str, Any]:
    """鸟狗式：左右肩 y 差、左右髋 y 差均应很小，max 差值越小越好。"""
    shoulder_delta = abs(keypoints[COCO_KEYPOINTS["left_shoulder"]][1] - keypoints[COCO_KEYPOINTS["right_shoulder"]][1])
    hip_delta = abs(keypoints[COCO_KEYPOINTS["left_hip"]][1] - keypoints[COCO_KEYPOINTS["right_hip"]][1])
    max_delta = max(shoulder_delta, hip_delta)

    # 连续评分：0.0 → 95, 0.03 → 85, 0.15 → 25
    raw = _linear_map(max_delta, best=0.0, worst=0.15, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "躯干稳定，肩和骨盆完全水平，手臂和腿向远处延伸！",
        "躯干较稳定，再收紧核心，让肩和骨盆保持水平。",
        "身体有轻微歪斜，请收紧核心，让肩和骨盆回到水平。",
        "身体明显歪斜，请先回到四足跪姿稳定躯干，再缓慢伸展。",
    )
    return _score_response(feedback, int(round(raw)), action_id="bird_dog")


# ---- dead_bug: 死虫式核心训练 ----

def _check_dead_bug(keypoints: list[list[float]]) -> dict[str, Any]:
    """死虫式：肩与髋 x 应对齐，偏移越小越好。"""
    shoulder_mid = midpoint(keypoints[COCO_KEYPOINTS["left_shoulder"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    hip_mid = midpoint(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    offset_x = abs(shoulder_mid[0] - hip_mid[0])

    # 连续评分：0.0 → 95, 0.04 → 80, 0.20 → 25
    raw = _linear_map(offset_x, best=0.0, worst=0.20, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "核心控制优秀，躯干稳定无歪斜，下背部贴地！",
        "核心控制良好，再收紧腹部让肩髋对齐。",
        "腰部有拱起趋势，请收紧腹部，让下背部贴近地面。",
        "腰部明显拱起，请先收腹让背部贴地，再缓慢交替手脚。",
    )
    return _score_response(feedback, int(round(raw)), action_id="dead_bug")


# ---- glute_bridge: 臀桥训练 ----

def _check_glute_bridge(keypoints: list[list[float]]) -> dict[str, Any]:
    """臀桥：髋部应高于膝和肩，抬起越高越好。"""
    shoulder_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    hip_y = (keypoints[COCO_KEYPOINTS["left_hip"]][1] + keypoints[COCO_KEYPOINTS["right_hip"]][1]) / 2
    knee_y = (keypoints[COCO_KEYPOINTS["left_knee"]][1] + keypoints[COCO_KEYPOINTS["right_knee"]][1]) / 2

    # 髋部抬起量：最低参考点与髋的 y 差（越大越好）
    baseline = max(shoulder_y, knee_y)
    lift = baseline - hip_y  # 正值 = 髋高于肩/膝基线

    # 连续评分：lift ≥ 0.08 → 95, 0.0 → 60, -0.05 → 25
    raw = _linear_map(lift, best=0.08, worst=-0.05, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "臀部充分抬起，肩髋膝连线平直，发力正确！",
        "臀部抬起良好，再收紧臀肌抬高一点，直到大腿与躯干成线。",
        "请继续抬高臀部，感受臀肌发力，直到肩髋膝接近一条直线。",
        "臀部几乎未抬起，请先屈膝仰卧，再用力收紧臀肌向上顶髋。",
    )
    return _score_response(feedback, int(round(raw)), action_id="glute_bridge")


# ---- wall_squat: 靠墙静蹲 ----

def _check_wall_squat(keypoints: list[list[float]]) -> dict[str, Any]:
    """靠墙静蹲：膝关节角度最优区间 90–100°，过小过大均扣分。"""
    angles = [
        calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]]),
        calculate_angle(keypoints[COCO_KEYPOINTS["right_hip"]], keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]]),
    ]
    knee_angle = min(angle for angle in angles if angle > 0)

    # 区间评分：opt=[90,105], bad=[50,160]
    raw = _range_score(knee_angle, opt_lo=90, opt_hi=105, bad_lo=50, bad_hi=160, max_score=95, min_score=25)

    if knee_angle < 85:
        detail = f"当前角度 {knee_angle:.0f}°，下蹲略深，请稍微站高一点。"
    elif knee_angle > 125:
        detail = f"当前角度 {knee_angle:.0f}°，下蹲幅度还不够，请沿墙缓慢下滑。"
    else:
        detail = f"当前角度 {knee_angle:.0f}°，角度合适，保持膝盖朝向脚尖。"

    feedback = _graded_feedback(
        raw,
        f"膝关节角度合适，保持膝盖朝向脚尖，非常标准！{detail}",
        f"角度接近理想范围，微调即可。{detail}",
        f"角度偏离较多。{detail}",
        f"角度偏离过大，请调整下蹲深度。{detail}",
    )
    return _score_response(feedback, int(round(raw)), action_id="wall_squat")


# ---- straight_leg_raise: 直腿抬高训练 ----

def _check_straight_leg_raise(keypoints: list[list[float]]) -> dict[str, Any]:
    """直腿抬高：膝关节角度越大越好（腿充分伸直）。"""
    angles = [
        calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]]),
        calculate_angle(keypoints[COCO_KEYPOINTS["right_hip"]], keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]]),
    ]
    knee_angle = max(angles)

    # 连续评分：≥ 175° → 95, 160° → 75, 135° → 25
    raw = _linear_map(knee_angle, best=175.0, worst=135.0, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "腿部完全伸直，抬腿过程缓慢控制，非常标准！",
        "腿部较直，再锁住膝盖，让腿完全伸直后抬起。",
        "膝盖有弯曲，请绷紧大腿前侧肌肉，锁住膝盖再抬腿。",
        "膝盖明显弯曲，请先将腿完全伸直绷紧，再缓慢抬起。",
    )
    return _score_response(feedback, int(round(raw)), action_id="straight_leg_raise")


# ---- quad_set: 股四头肌等长收缩 ----

def _check_quad_set(keypoints: list[list[float]]) -> dict[str, Any]:
    """股四头肌等长收缩：膝关节角度越大越好（充分伸直）。"""
    knee_angle = calculate_angle(
        keypoints[COCO_KEYPOINTS["left_hip"]],
        keypoints[COCO_KEYPOINTS["left_knee"]],
        keypoints[COCO_KEYPOINTS["left_ankle"]],
    )

    # 连续评分：≥ 175° → 95, 165° → 75, 140° → 25
    raw = _linear_map(knee_angle, best=175.0, worst=140.0, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "膝部完全伸直，股四头肌收缩到位，保持 5 秒！",
        "膝部较直，再绷紧大腿前侧肌肉，让膝关节完全打直。",
        "膝关节未完全伸直，请用力绷紧大腿前侧肌肉。",
        "膝关节明显弯曲，请先将腿放平，再用力收缩股四头肌。",
    )
    return _score_response(feedback, int(round(raw)), action_id="quad_set")


# ---- calf_stretch: 小腿后侧拉伸 ----

def _check_calf_stretch(keypoints: list[list[float]]) -> dict[str, Any]:
    """小腿后侧拉伸：后侧腿膝关节角度越大越好（充分伸直）。"""
    left_knee = calculate_angle(
        keypoints[COCO_KEYPOINTS["left_hip"]],
        keypoints[COCO_KEYPOINTS["left_knee"]],
        keypoints[COCO_KEYPOINTS["left_ankle"]],
    )
    right_knee = calculate_angle(
        keypoints[COCO_KEYPOINTS["right_hip"]],
        keypoints[COCO_KEYPOINTS["right_knee"]],
        keypoints[COCO_KEYPOINTS["right_ankle"]],
    )
    rear_knee_angle = max(left_knee, right_knee)

    # 连续评分：≥ 170° → 95, 158° → 72, 135° → 22
    raw = _linear_map(rear_knee_angle, best=170.0, worst=135.0, best_score=95, worst_score=22)

    feedback = _graded_feedback(
        raw,
        "后侧腿充分伸直，小腿后侧拉伸感明显！",
        "后侧腿较直，再蹬直膝盖，让小腿后侧有稳定拉伸感。",
        "后侧腿弯曲，请再伸直一些，小腿后侧才会有拉伸感。",
        "后侧腿明显弯曲，请先调整站姿，后脚跟着地，膝盖打直。",
    )
    return _score_response(feedback, int(round(raw)), action_id="calf_stretch")


# ---- ankle_pump: 踝泵运动 ----

def _check_ankle_pump(keypoints: list[list[float]]) -> dict[str, Any]:
    """踝泵运动：踝关节角度越远离 90° 越好（充分背伸/跖屈）。"""
    def _ankle_angle(knee, ankle):
        virt = [ankle[0], ankle[1] - 0.1, 0.0]
        return calculate_angle(knee, ankle, virt)

    left_angle = _ankle_angle(
        keypoints[COCO_KEYPOINTS["left_knee"]],
        keypoints[COCO_KEYPOINTS["left_ankle"]],
    )
    right_angle = _ankle_angle(
        keypoints[COCO_KEYPOINTS["right_knee"]],
        keypoints[COCO_KEYPOINTS["right_ankle"]],
    )
    active_angle = max(left_angle, right_angle)

    # 踝泵评分：越远离 90° 越好
    # 180° = 脚尖下踩到底（跖屈），0° = 脚尖上勾到底（背伸）
    deviation = abs(active_angle - 90.0)  # 偏离 90° 的量
    # deviation ≥ 70 → 95, deviation ≥ 40 → 80, deviation = 0 → 35
    raw = _linear_map(deviation, best=70.0, worst=0.0, best_score=95, worst_score=35)

    feedback = _graded_feedback(
        raw,
        "踝泵活动幅度充分，继续做脚尖上勾和下踩的交替！",
        "踝泵幅度较好，再加大一点，脚尖尽量上勾再缓慢下踩。",
        "请加大脚踝活动幅度，脚尖尽量向上勾再向下踩。",
        "脚踝活动幅度太小，请在无痛范围内尽量勾脚尖和踩脚尖。",
    )
    return _score_response(feedback, int(round(raw)), action_id="ankle_pump")


# ---- shoulder_pendulum: 肩关节钟摆运动 ----

def _check_shoulder_pendulum(keypoints: list[list[float]]) -> dict[str, Any]:
    """肩关节钟摆：手腕到肩距离越大越好（手臂放松下垂）。"""
    left_dist = calculate_distance(keypoints[COCO_KEYPOINTS["left_wrist"]], keypoints[COCO_KEYPOINTS["left_shoulder"]])
    right_dist = calculate_distance(keypoints[COCO_KEYPOINTS["right_wrist"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    max_dist = max(left_dist, right_dist)

    # 连续评分：≥ 0.35 → 95, 0.26 → 75, 0.16 → 25
    raw = _linear_map(max_dist, best=0.35, worst=0.16, best_score=95, worst_score=25)

    feedback = _graded_feedback(
        raw,
        "手臂完全放松下垂，利用身体轻微摆动带动手臂。",
        "手臂较放松，再让肩部下沉，手臂自然下垂摆动。",
        "手臂略紧张，请放松肩部，让手臂像钟摆一样自然下垂。",
        "手臂明显紧张未下垂，请先放松肩关节，让手臂完全垂下。",
    )
    return _score_response(feedback, int(round(raw)), action_id="shoulder_pendulum")


# ---- shoulder_external_rotation: 肩外旋弹力带训练 ----

def _check_shoulder_external_rotation(keypoints: list[list[float]]) -> dict[str, Any]:
    """肩外旋：肘到髋距离越小越好（肘夹紧身体）。"""
    left_elbow_hip = calculate_distance(keypoints[COCO_KEYPOINTS["left_elbow"]], keypoints[COCO_KEYPOINTS["left_hip"]])
    right_elbow_hip = calculate_distance(keypoints[COCO_KEYPOINTS["right_elbow"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    min_dist = min(left_elbow_hip, right_elbow_hip)

    # 连续评分：≤ 0.12 → 95, 0.18 → 75, 0.35 → 22
    raw = _linear_map(min_dist, best=0.12, worst=0.35, best_score=95, worst_score=22)

    feedback = _graded_feedback(
        raw,
        "肘部紧贴身体侧面，外旋方向正确，非常标准！",
        "肘部较贴近身体，再夹紧一点，然后缓慢外旋前臂。",
        "请把肘部夹紧身体侧面，再向外旋转前臂。",
        "肘部远离身体，请先将上臂紧贴躯干，再尝试外旋。",
    )
    return _score_response(feedback, int(round(raw)), action_id="shoulder_external_rotation")


# ========================================================================
# DeepRehabPile ML 评分动作（8 个）
# ========================================================================

def _check_ml_action(keypoints: list[list[float]], action_id: str) -> dict[str, Any]:
    """ML 动作的通用 Checker：读取 DeepRehabScorer 缓存的评分。"""
    scorer = get_scorer()
    result = scorer.get_result(action_id)
    if result is not None:
        return result

    total = scorer.total_frames(action_id)
    remaining = max(0, 300 - total)

    if not scorer.is_ready:
        return {
            "feedback": [f"AI 模型未加载，请检查模型文件。已采集 {total} 帧。"],
            "score": 0,
            "status": "error",
        }
    if remaining > 0:
        return {
            "feedback": [f"AI 动作评估中… 已采集 {total} 帧（还需 {remaining} 帧），请继续完成动作。"],
            "score": 0,
            "status": "warning",
        }
    return {
        "feedback": [f"AI 动作评估中… 已采集 {total} 帧，评分即将更新。"],
        "score": 0,
        "status": "warning",
    }


def _check_lifting_of_arms(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "lifting_of_arms")


def _check_shoulder_abduction_left(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "shoulder_abduction_left")


def _check_shoulder_abduction_right(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "shoulder_abduction_right")


def _check_shoulder_flexion_left(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "shoulder_flexion_left")


def _check_shoulder_flexion_right(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "shoulder_flexion_right")


def _check_shoulder_forward_elevation(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "shoulder_forward_elevation")


def _check_elbow_flexion_left(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "elbow_flexion_left")


def _check_elbow_flexion_right(keypoints: list[list[float]]) -> dict[str, Any]:
    return _check_ml_action(keypoints, "elbow_flexion_right")
