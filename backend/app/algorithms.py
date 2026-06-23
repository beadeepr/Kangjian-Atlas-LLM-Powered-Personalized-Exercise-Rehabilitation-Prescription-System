from __future__ import annotations

from typing import Any

import numpy as np


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


def _visibility_guard(action_id: str, visibility: list[float]) -> dict[str, Any] | None:
    required_map = {
        "neck_chin_tuck": [0, 7, 8, 11, 12],
        "chin_tuck": [0, 7, 8, 11, 12],
        "neck_side_bend": [0, 7, 8, 11, 12],
        "scapular_retraction": [7, 8, 11, 12],
        "thoracic_extension": [11, 12, 23, 24],
        "mckenzie_press_up": [11, 12, 13, 14, 15, 16, 23, 24],
        "pelvic_tilt": [11, 12, 23, 24, 25, 26],
        "bird_dog": [11, 12, 23, 24, 15, 16, 27, 28],
        "dead_bug": [11, 12, 23, 24, 25, 26],
        "glute_bridge": [11, 12, 23, 24, 25, 26],
        "wall_squat": [23, 24, 25, 26, 27, 28],
        "straight_leg_raise": [23, 24, 25, 26, 27, 28],
        "quad_set": [23, 25, 27],
        "calf_stretch": [23, 24, 25, 26, 27, 28, 29, 30],
        "ankle_pump": [25, 26, 27, 28, 31, 32],
        "shoulder_pendulum": [11, 12, 15, 16],
        "shoulder_external_rotation": [11, 12, 13, 14, 15, 16, 23, 24],
    }
    if not visibility:
        return None
    required = required_map.get(action_id, list(range(min(33, len(visibility)))))
    visible_count = sum(1 for index in required if index < len(visibility) and visibility[index] >= 0.5)
    if visible_count < max(2, int(len(required) * 0.65)):
        return {
            "feedback": ["关键关节识别不完整，请后退一点并确保目标部位完整入镜。"],
            "score": 35,
            "status": "warning",
        }
    return None


def analyze_pose(action_id: str, keypoints: list[list[float]], visibility: list[float]) -> dict[str, Any]:
    action_id = "neck_chin_tuck" if action_id == "chin_tuck" else action_id
    guard = _visibility_guard(action_id, visibility)
    if guard:
        return guard

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
    }
    checker = checkers.get(action_id)
    if not checker:
        return {"feedback": ["该动作暂未配置实时纠正规则，请先按动作说明完成。"], "score": 0, "status": "error"}
    return checker(keypoints)


def _check_neck_chin_tuck(keypoints: list[list[float]]) -> dict[str, Any]:
    nose = keypoints[0]
    ear_mid = midpoint(keypoints[7], keypoints[8])
    dist_nose_ear_x = abs(nose[0] - ear_mid[0])
    if dist_nose_ear_x > 0.06:
        return _score_response(["下巴回收还不够，请像做“双下巴”一样缓慢向后收。"], 72)
    return _score_response(["下巴回收到位，保持头颈竖直并放松肩部。"], 95)


def _check_neck_bend(keypoints: list[list[float]]) -> dict[str, Any]:
    left_ear = keypoints[7]
    right_ear = keypoints[8]
    left_shoulder = keypoints[11]
    right_shoulder = keypoints[12]
    nose = keypoints[0]
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
    shoulder_y = (keypoints[11][1] + keypoints[12][1]) / 2
    ear_y = (keypoints[7][1] + keypoints[8][1]) / 2
    if (ear_y - shoulder_y) < 0.12:
        return _score_response(["肩部有上提趋势，请先沉肩，再把肩胛骨向后下方夹紧。"], 72)
    return _score_response(["肩部下沉，肩胛后缩动作稳定。"], 92)


def _check_thoracic_extension(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_mid = midpoint(keypoints[11], keypoints[12])
    hip_mid = midpoint(keypoints[23], keypoints[24])
    if shoulder_mid[1] < hip_mid[1]:
        return _score_response(["胸椎伸展方向正确，注意不要用腰部过度代偿。"], 90)
    return _score_response(["身体略前倾，请坐直并从上背部向后伸展。"], 72)


def _check_mckenzie_press_up(keypoints: list[list[float]]) -> dict[str, Any]:
    left_elbow_angle = calculate_angle(keypoints[11], keypoints[13], keypoints[15])
    right_elbow_angle = calculate_angle(keypoints[12], keypoints[14], keypoints[16])
    elbow_angle = max(left_elbow_angle, right_elbow_angle)
    if elbow_angle > 155:
        return _score_response(["手臂伸展充分，胸部抬离地面，骨盆保持贴地。"], 90)
    return _score_response(["请用手臂力量缓慢撑起上半身，腰部不要出现锐痛。"], 72)


def _check_pelvic_tilt(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_mid_y = (keypoints[11][1] + keypoints[12][1]) / 2
    hip_mid_y = (keypoints[23][1] + keypoints[24][1]) / 2
    if abs(hip_mid_y - shoulder_mid_y) < 0.12:
        return _score_response(["收紧腹部，感受腰背轻贴地面，动作幅度保持小而稳定。"], 88)
    return _score_response(["请保持仰卧屈膝姿势，专注骨盆轻微后倾。"], 75)


def _check_bird_dog(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_delta = abs(keypoints[11][1] - keypoints[12][1])
    hip_delta = abs(keypoints[23][1] - keypoints[24][1])
    if shoulder_delta > 0.06 or hip_delta > 0.06:
        return _score_response(["身体出现歪斜，请收紧核心，让肩和骨盆保持水平。"], 70)
    return _score_response(["躯干稳定，手臂和腿向远处延伸，保持慢速控制。"], 92)


def _check_dead_bug(keypoints: list[list[float]]) -> dict[str, Any]:
    hip_mid_z = (keypoints[23][2] + keypoints[24][2]) / 2
    shoulder_mid_z = (keypoints[11][2] + keypoints[12][2]) / 2
    if hip_mid_z > shoulder_mid_z + 0.05:
        return _score_response(["腰部有拱起趋势，请收紧腹部，让下背部贴近地面。"], 68)
    return _score_response(["核心控制良好，继续缓慢交替手脚。"], 90)


def _check_glute_bridge(keypoints: list[list[float]]) -> dict[str, Any]:
    shoulder_y = (keypoints[11][1] + keypoints[12][1]) / 2
    hip_y = (keypoints[23][1] + keypoints[24][1]) / 2
    knee_y = (keypoints[25][1] + keypoints[26][1]) / 2
    if hip_y < knee_y and hip_y < shoulder_y:
        return _score_response(["臀部发力抬起，肩、髋、膝连线较好。"], 92)
    return _score_response(["请继续抬高臀部，直到大腿与躯干接近一条直线。"], 72)


def _check_wall_squat(keypoints: list[list[float]]) -> dict[str, Any]:
    angles = [
        calculate_angle(keypoints[23], keypoints[25], keypoints[27]),
        calculate_angle(keypoints[24], keypoints[26], keypoints[28]),
    ]
    knee_angle = min(angle for angle in angles if angle > 0)
    if knee_angle < 85:
        return _score_response(["下蹲略深，请稍微站高一点，避免膝关节压力过大。"], 72)
    if knee_angle > 125:
        return _score_response(["下蹲幅度还不够，请沿墙缓慢下滑。"], 78)
    return _score_response(["膝关节角度合适，保持膝盖朝向脚尖。"], 94)


def _check_straight_leg_raise(keypoints: list[list[float]]) -> dict[str, Any]:
    angles = [
        calculate_angle(keypoints[23], keypoints[25], keypoints[27]),
        calculate_angle(keypoints[24], keypoints[26], keypoints[28]),
    ]
    knee_angle = max(angles)
    if knee_angle > 160:
        return _score_response(["腿部伸直，抬腿过程保持缓慢。"], 90)
    return _score_response(["请锁住膝盖，保持腿伸直后再抬起。"], 70)


def _check_quad_set(keypoints: list[list[float]]) -> dict[str, Any]:
    knee_angle = calculate_angle(keypoints[23], keypoints[25], keypoints[27])
    if knee_angle < 165:
        return _score_response(["膝关节还没有完全伸直，请绷紧大腿前侧肌肉。"], 72)
    return _score_response(["膝部伸直，股四头肌收缩到位，保持 5 秒。"], 92)


def _check_calf_stretch(keypoints: list[list[float]]) -> dict[str, Any]:
    left_knee = calculate_angle(keypoints[23], keypoints[25], keypoints[27])
    right_knee = calculate_angle(keypoints[24], keypoints[26], keypoints[28])
    rear_knee_angle = max(left_knee, right_knee)
    ankle_y = min(keypoints[27][1], keypoints[28][1])
    heel_y = min(keypoints[29][1], keypoints[30][1])
    feedback = []
    score = 90
    if rear_knee_angle < 158:
        feedback.append("后侧腿需要再伸直一些，小腿后侧才会有稳定拉伸感。")
        score -= 18
    else:
        feedback.append("后侧腿伸直较好，保持身体向墙面缓慢前移。")
    if heel_y < ankle_y - 0.04:
        feedback.append("注意脚跟不要明显抬起，尽量贴近地面。")
        score -= 12
    else:
        feedback.append("脚跟位置稳定，拉伸过程中保持呼吸。")
    return _score_response(feedback, score)


def _check_ankle_pump(keypoints: list[list[float]]) -> dict[str, Any]:
    left_angle = calculate_angle(keypoints[25], keypoints[27], keypoints[31])
    right_angle = calculate_angle(keypoints[26], keypoints[28], keypoints[32])
    active_angle = max(left_angle, right_angle)
    if active_angle < 70 or active_angle > 145:
        return _score_response(["踝泵幅度较充分，继续做脚尖上勾和下踩的交替动作。"], 90)
    return _score_response(["请加大脚踝活动幅度，脚尖尽量上勾再缓慢下踩。"], 76)


def _check_shoulder_pendulum(keypoints: list[list[float]]) -> dict[str, Any]:
    left_dist = calculate_distance(keypoints[15], keypoints[11])
    right_dist = calculate_distance(keypoints[16], keypoints[12])
    if max(left_dist, right_dist) < 0.26:
        return _score_response(["手臂略紧张，请放松肩部，让手臂自然下垂摆动。"], 74)
    return _score_response(["手臂下垂自然，利用身体轻微摆动带动手臂。"], 90)


def _check_shoulder_external_rotation(keypoints: list[list[float]]) -> dict[str, Any]:
    left_elbow_hip = calculate_distance(keypoints[13], keypoints[23])
    right_elbow_hip = calculate_distance(keypoints[14], keypoints[24])
    if min(left_elbow_hip, right_elbow_hip) < 0.18:
        return _score_response(["肘部贴近身体，外旋方向正确。"], 92)
    return _score_response(["请把肘部夹紧身体侧面，再缓慢向外旋转前臂。"], 72)
