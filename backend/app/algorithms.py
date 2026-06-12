import numpy as np
from typing import List, Dict, Any

def calculate_angle(a: List[float], b: List[float], c: List[float]) -> float:
    """
    计算三点构成的夹角 (b为顶点)，返回角度制 (0-180)
    a, b, c: [x, y, z]
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    ba = a - b
    bc = c - b
    
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    
    return np.degrees(angle)

def calculate_distance(p1: List[float], p2: List[float]) -> float:
    """计算两点间的欧几里得距离"""
    p1 = np.array(p1)
    p2 = np.array(p2)
    return np.linalg.norm(p1 - p2)

def analyze_pose(action_id: str, keypoints: List[List[float]], visibility: List[float]) -> Dict[str, Any]:
    """
    主入口函数：根据 action_id 分发到不同的算法逻辑
    """
    # 1. 检查 visibility，如果关键点遮挡严重，直接返回错误
    if not visibility or sum(visibility) / len(visibility) < 0.5:
        return {
            "feedback": ["检测到遮挡严重，请调整位置或光线"],
            "score": 0,
            "status": "error"
        }

    # 2. 分发逻辑
    if action_id == "wall_squat":
        return _check_wall_squat(keypoints)
    elif action_id == "neck_side_bend":
        return _check_neck_bend(keypoints)
    else:
        return {
            "feedback": ["该动作算法尚未实现"],
            "score": 0,
            "status": "error"
        }

def _check_wall_squat(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 索引参考 MediaPipe Pose Landmarks
    hip_l = keypoints[23]
    knee_l = keypoints[25]
    ankle_l = keypoints[27]
    
    angle = calculate_angle(hip_l, knee_l, ankle_l)
    
    feedback = []
    score = 100
    
    if angle < 90:
        feedback.append("膝关节角度过小，请站起一点。")
        score -= 20
    elif angle > 120:
        feedback.append("膝关节角度过大，请蹲深一点。")
        score -= 15
    else:
        feedback.append("动作标准，继续保持。")
        
    return {
        "feedback": feedback,
        "score": score,
        "status": "ok" if score >= 80 else "warning"
    }

def _check_neck_bend(keypoints: List[List[float]]) -> Dict[str, Any]:
    """
    颈部侧屈算法实现
    关键点索引 (MediaPipe Pose):
    7: Left Ear, 8: Right Ear
    11: Left Shoulder, 12: Right Shoulder
    0: Nose
    """
    feedback = []
    score = 100
    
    left_ear = keypoints[7]
    right_ear = keypoints[8]
    left_shoulder = keypoints[11]
    right_shoulder = keypoints[12]
    nose = keypoints[0]
    
    # 1. 计算左右耳到同侧肩膀的距离
    dist_left = calculate_distance(left_ear, left_shoulder)
    dist_right = calculate_distance(right_ear, right_shoulder)
    
    # 2. 计算肩膀中点和鼻子的X坐标，判断身体是否正直
    shoulder_mid_x = (left_shoulder[0] + right_shoulder[0]) / 2
    nose_x = nose[0]
    # 如果鼻子偏离肩膀中线超过一定阈值，说明用户在转头或斜身
    is_facing_forward = abs(nose_x - shoulder_mid_x) < 0.08 
    
    if not is_facing_forward:
        return {
            "feedback": ["请正对摄像头，不要转动身体或头部"],
            "score": 50,
            "status": "warning"
        }
    
    # 3. 判定拉伸方向与程度
    # 假设目标是将耳朵靠近肩膀，距离越小越好。
    # 经验阈值：归一化距离 < 0.15 认为拉伸较好
    threshold_good = 0.15
    threshold_excellent = 0.10
    
    # 找出哪一侧更近（即正在拉伸的一侧）
    if dist_left < dist_right:
        # 左侧拉伸
        if dist_left < threshold_excellent:
            feedback.append("左侧拉伸非常到位！保持呼吸。")
            score = 100
        elif dist_left < threshold_good:
            feedback.append("左侧拉伸良好，可以再低一点点。")
            score = 85
        else:
            feedback.append("请尝试将左耳向左肩靠近。")
            score = 60
    else:
        # 右侧拉伸
        if dist_right < threshold_excellent:
            feedback.append("右侧拉伸非常到位！保持呼吸。")
            score = 100
        elif dist_right < threshold_good:
            feedback.append("右侧拉伸良好，可以再低一点点。")
            score = 85
        else:
            feedback.append("请尝试将右耳向右肩靠近。")
            score = 60
            
    status = "ok" if score >= 80 else "warning"
    
    return {
        "feedback": feedback,
        "score": score,
        "status": status
    }