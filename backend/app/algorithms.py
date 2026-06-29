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


def _score_response(feedback: list[str], score: int) -> dict[str, Any]:
    score = max(0, min(100, int(score)))
    if score >= 80:
        status = "ok"
    elif score >= 45:
        status = "warning"
    else:
        status = "error"
    return {"feedback": feedback, "score": score, "status": status}


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
        # ---- ML 动作：需要上身关键点 ----
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
        if index >= len(visibility) or visibility[index] < 0.8:
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


def analyze_pose(action_id: str, keypoints: list[list[float]], visibility: list[float]) -> dict[str, Any]:
    action_id = "neck_chin_tuck" if action_id == "chin_tuck" else action_id
    if action_id in ML_ACTIONS and len(keypoints) <= 17:
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
        # ---- DeepRehabPile ML 评分动作 ----
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


def _check_neck_chin_tuck(keypoints: list[list[float]]) -> dict[str, Any]:
    nose = keypoints[COCO_KEYPOINTS["nose"]]
    ear_mid = midpoint(keypoints[COCO_KEYPOINTS["left_ear"]], keypoints[COCO_KEYPOINTS["right_ear"]])
    dist_nose_ear_x = abs(nose[0] - ear_mid[0])
    if dist_nose_ear_x > 0.06:
        return _score_response(["下巴回收还不够，请像做“双下巴”一样缓慢向后收。"], 72)
    return _score_response(["下巴回收到位，保持头颈竖直并放松肩部。"], 95)


def _check_neck_bend(keypoints: list[list[float]]) -> dict[str, Any]:
    left_ear = keypoints[COCO_KEYPOINTS["left_ear"]]
    right_ear = keypoints[COCO_KEYPOINTS["right_ear"]]
    left_shoulder = keypoints[COCO_KEYPOINTS["left_shoulder"]]
    right_shoulder = keypoints[COCO_KEYPOINTS["right_shoulder"]]
    nose = keypoints[COCO_KEYPOINTS["nose"]]
    shoulder_mid_x = (left_shoulder[0] + right_shoulder[0]) / 2
    if abs(nose[0] - shoulder_mid_x) > 0.09:
        return _score_response(["请正对摄像头，避免转头或身体旋转。"], 55)

    dist_left = calculate_distance(left_ear, left_shoulder)
    dist_right = calculate_distance(right_ear, right_shoulder)
    active_dist = min(dist_left, dist_right)
    if active_dist < 0.10:
        return _score_response(["侧屈幅度很好，保持呼吸，不要耸肩。"], 96)
    if active_dist < 0.15:
        return _score_response(["侧屈方向正确，可以再轻一点靠近同侧肩部。"], 85)
    return _score_response(["请缓慢将耳朵向同侧肩部靠近，感受颈侧拉伸。"], 65)


def _check_scapular_retraction(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    ear_y = (keypoints[COCO_KEYPOINTS["left_ear"]][1] + keypoints[COCO_KEYPOINTS["right_ear"]][1]) / 2
    if (ear_y - shoulder_y) < 0.12:
        return _score_response(["肩部有上提趋势，请先沉肩，再把肩胛骨向后下方夹紧。"], 72)
    return _score_response(["肩部下沉，肩胛后缩动作稳定。"], 92)


def _check_thoracic_extension(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_mid = midpoint(keypoints[COCO_KEYPOINTS["left_shoulder"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    hip_mid = midpoint(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    if shoulder_mid[1] < hip_mid[1]:
        return _score_response(["胸椎伸展方向正确，注意不要用腰部过度代偿。"], 90)
    return _score_response(["身体略前倾，请坐直并从上背部向后伸展。"], 72)


def _check_mckenzie_press_up(keypoints: list[list[float]]) -> dict[str, Any]:
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
    if elbow_angle > 155:
        return _score_response(["手臂伸展充分，胸部抬离地面，骨盆保持贴地。"], 90)
    return _score_response(["请用手臂力量缓慢撑起上半身，腰部不要出现锐痛。"], 72)


def _check_pelvic_tilt(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_mid_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    hip_mid_y = (keypoints[COCO_KEYPOINTS["left_hip"]][1] + keypoints[COCO_KEYPOINTS["right_hip"]][1]) / 2
    if abs(hip_mid_y - shoulder_mid_y) < 0.12:
        return _score_response(["收紧腹部，感受腰背轻贴地面，动作幅度保持小而稳定。"], 88)
    return _score_response(["请保持仰卧屈膝姿势，专注骨盆轻微后倾。"], 75)


def _check_bird_dog(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_delta = abs(keypoints[COCO_KEYPOINTS["left_shoulder"]][1] - keypoints[COCO_KEYPOINTS["right_shoulder"]][1])
    hip_delta = abs(keypoints[COCO_KEYPOINTS["left_hip"]][1] - keypoints[COCO_KEYPOINTS["right_hip"]][1])
    if shoulder_delta > 0.06 or hip_delta > 0.06:
        return _score_response(["身体出现歪斜，请收紧核心，让肩和骨盆保持水平。"], 70)
    return _score_response(["躯干稳定，手臂和腿向远处延伸，保持慢速控制。"], 92)


def _check_dead_bug(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_mid = midpoint(keypoints[COCO_KEYPOINTS["left_shoulder"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    hip_mid = midpoint(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    if abs(shoulder_mid[0] - hip_mid[0]) > 0.08:
        return _score_response(["腰部有拱起趋势，请收紧腹部，让下背部贴近地面。"], 68)
    return _score_response(["核心控制良好，继续缓慢交替手脚。"], 90)


def _check_glute_bridge(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_y = (keypoints[COCO_KEYPOINTS["left_shoulder"]][1] + keypoints[COCO_KEYPOINTS["right_shoulder"]][1]) / 2
    hip_y = (keypoints[COCO_KEYPOINTS["left_hip"]][1] + keypoints[COCO_KEYPOINTS["right_hip"]][1]) / 2
    knee_y = (keypoints[COCO_KEYPOINTS["left_knee"]][1] + keypoints[COCO_KEYPOINTS["right_knee"]][1]) / 2
    if hip_y < knee_y and hip_y < shoulder_y:
        return _score_response(["臀部发力抬起，肩、髋、膝连线较好。"], 92)
    return _score_response(["请继续抬高臀部，直到大腿与躯干接近一条直线。"], 72)


def _check_wall_squat(keypoints: list[list[float]]) -> dict[str, Any]:
    angles = [
        calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]]),
        calculate_angle(keypoints[COCO_KEYPOINTS["right_hip"]], keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]]),
    ]
    knee_angle = min(angle for angle in angles if angle > 0)
    if knee_angle < 85:
        return _score_response(["下蹲略深，请稍微站高一点，避免膝关节压力过大。"], 72)
    if knee_angle > 125:
        return _score_response(["下蹲幅度还不够，请沿墙缓慢下滑。"], 78)
    return _score_response(["膝关节角度合适，保持膝盖朝向脚尖。"], 94)


def _check_straight_leg_raise(keypoints: list[list[float]]) -> dict[str, Any]:
    angles = [
        calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]]),
        calculate_angle(keypoints[COCO_KEYPOINTS["right_hip"]], keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]]),
    ]
    knee_angle = max(angles)
    if knee_angle > 160:
        return _score_response(["腿部伸直，抬腿过程保持缓慢。"], 90)
    return _score_response(["请锁住膝盖，保持腿伸直后再抬起。"], 70)


def _check_quad_set(keypoints: list[list[float]]) -> dict[str, Any]:
    knee_angle = calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]])
    if knee_angle < 165:
        return _score_response(["膝关节还没有完全伸直，请绷紧大腿前侧肌肉。"], 72)
    return _score_response(["膝部伸直，股四头肌收缩到位，保持 5 秒。"], 92)


def _check_calf_stretch(keypoints: list[list[float]]) -> dict[str, Any]:
    left_knee = calculate_angle(keypoints[COCO_KEYPOINTS["left_hip"]], keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]])
    right_knee = calculate_angle(keypoints[COCO_KEYPOINTS["right_hip"]], keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]])
    rear_knee_angle = max(left_knee, right_knee)
    if rear_knee_angle < 158:
        return _score_response(["后侧腿需要再伸直一些，小腿后侧才会有稳定拉伸感。"], 72)
    return _score_response(["后侧腿伸直较好，保持身体向墙面缓慢前移。"], 90)


def _check_ankle_pump(keypoints: list[list[float]]) -> dict[str, Any]:
    vertical_up = [0.0, -1.0, 0.0]
    left_angle = calculate_angle(keypoints[COCO_KEYPOINTS["left_knee"]], keypoints[COCO_KEYPOINTS["left_ankle"]], [keypoints[COCO_KEYPOINTS["left_ankle"]][0], keypoints[COCO_KEYPOINTS["left_ankle"]][1] - 0.1, 0.0])
    right_angle = calculate_angle(keypoints[COCO_KEYPOINTS["right_knee"]], keypoints[COCO_KEYPOINTS["right_ankle"]], [keypoints[COCO_KEYPOINTS["right_ankle"]][0], keypoints[COCO_KEYPOINTS["right_ankle"]][1] - 0.1, 0.0])
    active_angle = max(left_angle, right_angle)
    if active_angle < 70 or active_angle > 145:
        return _score_response(["踝泵幅度较充分，继续做脚尖上勾和下踩的交替动作。"], 90)
    return _score_response(["请加大脚踝活动幅度，脚尖尽量上勾再缓慢下踩。"], 76)


def _check_shoulder_pendulum(keypoints: list[list[float]]) -> dict[str, Any]:
    left_dist = calculate_distance(keypoints[COCO_KEYPOINTS["left_wrist"]], keypoints[COCO_KEYPOINTS["left_shoulder"]])
    right_dist = calculate_distance(keypoints[COCO_KEYPOINTS["right_wrist"]], keypoints[COCO_KEYPOINTS["right_shoulder"]])
    if max(left_dist, right_dist) < 0.26:
        return _score_response(["手臂略紧张，请放松肩部，让手臂自然下垂摆动。"], 74)
    return _score_response(["手臂下垂自然，利用身体轻微摆动带动手臂。"], 90)


def _check_shoulder_external_rotation(keypoints: list[list[float]]) -> dict[str, Any]:
    left_elbow_hip = calculate_distance(keypoints[COCO_KEYPOINTS["left_elbow"]], keypoints[COCO_KEYPOINTS["left_hip"]])
    right_elbow_hip = calculate_distance(keypoints[COCO_KEYPOINTS["right_elbow"]], keypoints[COCO_KEYPOINTS["right_hip"]])
    if min(left_elbow_hip, right_elbow_hip) < 0.18:
        return _score_response(["肘部贴近身体，外旋方向正确。"], 92)
    return _score_response(["请把肘部夹紧身体侧面，再缓慢向外旋转前臂。"], 72)


# ============================================================================
# DeepRehabPile ML 评分动作（8 个新增）
# ============================================================================
# 这些动作不使用传统的几何规则评分，而是通过 DeepRehabPile 模型
# 对一段骨架序列进行推理。每帧的评分结果来自模型缓存。


def _check_ml_action(keypoints: list[list[float]], action_id: str) -> dict[str, Any]:
    """ML 动作的通用 Checker：读取 DeepRehabScorer 缓存的评分。"""
    scorer = get_scorer()
    result = scorer.get_result(action_id)
    if result is not None:
        return result

    # 模型尚未产生结果：提示正在进行 AI 评估
    buf_size = scorer.buffer_size(action_id)
    return {
        "feedback": [f"AI 动作评估中… 已采集 {buf_size} 帧，请继续完成动作。"],
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
