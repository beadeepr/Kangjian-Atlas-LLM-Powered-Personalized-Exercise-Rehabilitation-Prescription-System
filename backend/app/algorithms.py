import numpy as np
from typing import List, Dict, Any

def calculate_angle(a: List[float], b: List[float], c: List[float]) -> float:
    """计算三点构成的夹角 (b为顶点)"""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

def calculate_distance(p1: List[float], p2: List[float]) -> float:
    """计算两点间的欧几里得距离"""
    return np.linalg.norm(np.array(p1) - np.array(p2))

def analyze_pose(action_id: str, keypoints: List[List[float]], visibility: List[float]) -> Dict[str, Any]:

    if action_id == "neck_chin_tuck":
        return _check_neck_chin_tuck(keypoints)
    elif action_id == "neck_side_bend":
        return _check_neck_bend(keypoints)
    elif action_id == "scapular_retraction":
        return _check_scapular_retraction(keypoints)
    elif action_id == "thoracic_extension":
        return _check_thoracic_extension(keypoints)
    elif action_id == "mckenzie_press_up":
        return _check_mckenzie_press_up(keypoints)
    elif action_id == "pelvic_tilt":
        return _check_pelvic_tilt(keypoints)
    elif action_id == "bird_dog":
        return _check_bird_dog(keypoints)
    elif action_id == "dead_bug":
        return _check_dead_bug(keypoints)
    elif action_id == "glute_bridge":
        return _check_glute_bridge(keypoints)
    elif action_id == "wall_squat":
        return _check_wall_squat(keypoints)
    elif action_id == "straight_leg_raise":
        return _check_straight_leg_raise(keypoints)
    elif action_id == "quad_set":
        return _check_quad_set(keypoints)
    elif action_id == "shoulder_pendulum":
        return _check_shoulder_pendulum(keypoints)
    elif action_id == "shoulder_external_rotation":
        return _check_shoulder_external_rotation(keypoints)
    else:
        return {"feedback": ["该动作算法尚未实现"], "score": 0, "status": "error"}

# --- 颈部与肩部动作 ---

def _check_neck_chin_tuck(keypoints: List[List[float]]) -> Dict[str, Any]:
    nose = keypoints[0]
    ear_l = keypoints[7]
    shoulder_mid = [(keypoints[11][i] + keypoints[12][i])/2 for i in range(3)]
    
    # 简单的水平位移判定：鼻子相对于耳朵的位置
    # 回收时，鼻子的 x 坐标应接近耳朵的 x 坐标（在正脸情况下）
    dist_nose_ear_x = abs(nose[0] - ear_l[0])
    
    feedback = []
    score = 100
    
    if dist_nose_ear_x > 0.05: # 阈值需根据实际摄像头距离微调
        feedback.append("请缓慢将下巴向后回收，感觉后颈有拉伸感。")
        score -= 20
    else:
        feedback.append("下巴回收到位，保持头部正直。")
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_neck_bend(keypoints: List[List[float]]) -> Dict[str, Any]:
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
    
    return {"feedback": feedback,"score": score,"status": status}
def _check_scapular_retraction(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 通过双肩宽度变化或肩胛骨位置判定
    shoulder_y = (keypoints[11][1] + keypoints[12][1]) / 2
    ear_y = (keypoints[7][1] + keypoints[8][1]) / 2
    
    feedback = []
    score = 100
    
    # 如果肩膀离耳朵太近，说明耸肩了
    if (ear_y - shoulder_y) < 0.15: 
        feedback.append("请放松肩膀，不要耸肩，专注于肩胛骨向后夹紧。")
        score -= 20
    else:
        feedback.append("肩膀下沉，肩胛骨后缩动作标准。")
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_thoracic_extension(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 胸椎伸展：看上半身是否挺直，肩膀是否在髋部后方（坐姿时）
    shoulder_mid = [(keypoints[11][i] + keypoints[12][i])/2 for i in range(3)]
    hip_mid = [(keypoints[23][i] + keypoints[24][i])/2 for i in range(3)]
    
    feedback = []
    score = 100
    
    # 简单判定：肩膀 y 坐标高于髋部且背部挺直
    if shoulder_mid[1] < hip_mid[1]: # y越小越靠上
        feedback.append("挺胸抬头，感受胸椎向后伸展。")
    else:
        feedback.append("身体有些前倾，请坐直并向上延伸脊柱。")
        score -= 20
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

# --- 腰部与核心动作 ---

def _check_mckenzie_press_up(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 俯卧撑式伸展：看肘关节角度和上半身抬起程度
    elbow_angle = calculate_angle(keypoints[13], keypoints[15], keypoints[17]) # 左臂为例
    
    feedback = []
    score = 100
    
    if elbow_angle > 160: # 手臂伸直
        feedback.append("手臂伸直，胸部抬离地面，注意腰部不要产生锐痛。")
    else:
        feedback.append("请用手臂力量将上半身撑起。")
        score -= 20
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_pelvic_tilt(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 骨盆后倾：仰卧位。比较髋部(ASIS)与肩部在垂直方向(y)的相对位置，并结合膝盖弯曲程度。
    shoulder_mid_y = (keypoints[11][1] + keypoints[12][1]) / 2
    hip_mid_y = (keypoints[23][1] + keypoints[24][1]) / 2
    knee_mid_y = (keypoints[25][1] + keypoints[26][1]) / 2
    
    feedback = []
    score = 100
    
    # 简单判定：如果髋部和肩部几乎在同一水平线，且膝盖弯曲，通常处于准备或完成状态
    # 真正的后倾很难仅凭 2D/3D 点精确捕捉，这里主要提示用户感受腹部发力
    if abs(hip_mid_y - shoulder_mid_y) < 0.1:
        feedback.append("请呼气，收紧腹部，感觉腰背向下压向床面。")
    else:
        feedback.append("保持仰卧姿势，专注于骨盆的微小转动。")
        
    return {"feedback": feedback, "score": score, "status": "ok"}

def _check_bird_dog(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 鸟狗式：四点跪姿，对侧手脚伸直。检查肩膀连线是否水平，以及抬起的手脚是否达到一定高度。
    left_shoulder = keypoints[11]
    right_shoulder = keypoints[12]
    left_hip = keypoints[23]
    right_hip = keypoints[24]
    
    # 计算肩膀连线的倾斜角
    delta_y = left_shoulder[1] - right_shoulder[1]
    delta_x = left_shoulder[0] - right_shoulder[0]
    tilt_angle = np.degrees(np.arctan2(delta_y, delta_x)) if abs(delta_x) > 0.01 else 0
    
    feedback = []
    score = 100
    
    # 如果肩膀倾斜超过 10 度，说明核心不稳
    if abs(tilt_angle) > 10:
        feedback.append("身体有些歪斜，请收紧核心，保持背部像桌子一样平。")
        score -= 20
    else:
        feedback.append("保持平衡，手臂和腿向远处延伸。")
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_dead_bug(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 死虫式：仰卧，四肢运动。重点监测腰部是否离开地面。通过比较腰部关键点(如髋部)与肩部/膝部的相对深度(z)或高度(y)。
    hip_mid_z = (keypoints[23][2] + keypoints[24][2]) / 2
    shoulder_mid_z = (keypoints[11][2] + keypoints[12][2]) / 2
    
    feedback = []
    score = 100
    
    # 在 MediaPipe 中，z 轴表示深度。如果腰部(z)明显小于肩部(z)，说明腰拱起来了
    if hip_mid_z > shoulder_mid_z + 0.05: 
        feedback.append("注意！腰部拱起了，请用力将肚脐拉向脊柱，贴紧地面。")
        score -= 30
    else:
        feedback.append("很好，保持下背部紧贴地面，缓慢交替手脚。")
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}
def _check_glute_bridge(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 臀桥：髋部抬起，肩髋膝一线
    shoulder_y = (keypoints[11][1] + keypoints[12][1]) / 2
    hip_y = (keypoints[23][1] + keypoints[24][1]) / 2
    knee_y = (keypoints[25][1] + keypoints[26][1]) / 2
    
    feedback = []
    score = 100
    
    # 髋部应该高于膝盖和肩膀
    if hip_y < knee_y and hip_y < shoulder_y:
        feedback.append("臀部发力抬起，身体呈一条直线。")
    else:
        feedback.append("请继续抬高臀部，直到大腿与躯干成一直线。")
        score -= 20
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

# --- 膝关节动作 ---

def _check_wall_squat(keypoints: List[List[float]]) -> Dict[str, Any]:
    hip_l = keypoints[23]
    knee_l = keypoints[25]
    ankle_l = keypoints[27]
    angle = calculate_angle(hip_l, knee_l, ankle_l)
    
    feedback = []
    score = 100
    if angle < 90:
        feedback.append("蹲得太深，请稍微站起。")
        score -= 20
    elif angle > 120:
        feedback.append("蹲得不够，请继续下蹲。")
        score -= 15
    else:
        feedback.append("膝盖角度完美！")
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_straight_leg_raise(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 直腿抬高：膝关节保持伸直，腿部抬起
    hip = keypoints[23]
    knee = keypoints[25]
    ankle = keypoints[27]
    
    knee_angle = calculate_angle(hip, knee, ankle)
    feedback = []
    score = 100
    
    if knee_angle > 160: # 腿是直的
        feedback.append("腿部伸直，缓慢抬高。")
    else:
        feedback.append("请锁住膝盖，保持腿部伸直再抬起。")
        score -= 20
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

def _check_quad_set(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 股四头肌等长收缩：坐姿或仰卧，膝下垫毛巾。监测膝关节角度是否保持在接近 180 度的伸直状态。
    hip = keypoints[23]
    knee = keypoints[25]
    ankle = keypoints[27]
    
    knee_angle = calculate_angle(hip, knee, ankle)
    feedback = []
    score = 100
    
    # 要求膝关节完全伸直 (接近 180 度)
    if knee_angle < 165:
        feedback.append("请将腿完全伸直，绷紧大腿前侧肌肉。")
        score -= 20
    else:
        feedback.append("保持腿部伸直，用力向下压毛巾，坚持 5 秒。")
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}

# --- 肩部动作 ---

def _check_shoulder_pendulum(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 钟摆运动：身体前倾，手臂自然下垂画圈。检测手腕关键点相对于肩膀的位移幅度。
    wrist = keypoints[15] # 以左手为例
    shoulder = keypoints[11]
    
    # 计算手腕到肩膀的距离
    dist = calculate_distance(wrist, shoulder)
    
    feedback = []
    score = 100
    
    # 钟摆运动要求手臂放松，距离应接近臂长。如果距离过短，说明用户在用力缩臂
    if dist < 0.3: # 归一化距离
        feedback.append("请放松肩膀，让手臂像钟摆一样自然摆动，不要用力。")
        score -= 15
    else:
        feedback.append("利用身体的惯性带动画圈，动作要轻柔。")
        
    return {"feedback": feedback, "score": score, "status": "ok"}

def _check_shoulder_external_rotation(keypoints: List[List[float]]) -> Dict[str, Any]:
    # 肩外旋：大臂夹紧身体，小臂向外转动
    # 检查肘部是否贴近身体
    elbow = keypoints[13]
    hip = keypoints[23]
    dist_elbow_hip = calculate_distance(elbow, hip)
    
    feedback = []
    score = 100
    
    if dist_elbow_hip < 0.15: # 肘部贴近身体
        feedback.append("大臂夹紧身体，小臂向外旋转。")
    else:
        feedback.append("请注意将大臂贴近身体侧面，不要张开。")
        score -= 20
        
    return {"feedback": feedback, "score": score, "status": "ok" if score >= 80 else "warning"}