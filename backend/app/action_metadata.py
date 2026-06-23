from __future__ import annotations


CATEGORY_BY_ID = {
    "neck_chin_tuck": "姿势矫正",
    "chin_tuck": "姿势矫正",
    "neck_side_bend": "拉伸训练",
    "scapular_retraction": "力量训练",
    "thoracic_extension": "活动度训练",
    "cat_cow": "活动度训练",
    "pelvic_tilt": "核心控制",
    "bird_dog": "核心稳定",
    "dead_bug": "核心稳定",
    "glute_bridge": "力量训练",
    "wall_squat": "力量训练",
    "straight_leg_raise": "力量训练",
    "quad_set": "等长收缩",
    "calf_stretch": "拉伸训练",
    "ankle_pump": "活动度训练",
    "shoulder_pendulum": "活动度训练",
    "shoulder_external_rotation": "力量训练",
    "mckenzie_press_up": "活动度训练",
}

DIFFICULTY_BY_CATEGORY = {
    "姿势矫正": "初级",
    "拉伸训练": "初级",
    "活动度训练": "初级",
    "等长收缩": "初级",
    "核心控制": "初级",
    "核心稳定": "中级",
    "力量训练": "中级",
}

MUSCLES_BY_REGION = {
    "颈部": ["颈深屈肌", "上斜方肌", "肩胛提肌"],
    "肩部": ["肩袖肌群", "菱形肌", "前锯肌", "斜方肌中下束"],
    "腰部": ["腹横肌", "多裂肌", "竖脊肌", "臀大肌"],
    "膝关节": ["股四头肌", "腘绳肌", "臀中肌"],
    "踝关节": ["腓肠肌", "比目鱼肌", "胫前肌"],
}

STAGE_BY_CATEGORY = {
    "姿势矫正": "疼痛缓解期/姿势恢复期",
    "拉伸训练": "疼痛缓解期/活动度恢复期",
    "活动度训练": "活动度恢复期",
    "等长收缩": "术后早期/力量启动期",
    "核心控制": "稳定控制建立期",
    "核心稳定": "功能恢复期",
    "力量训练": "力量恢复期",
}

RISK_BY_CATEGORY = {
    "姿势矫正": "低",
    "拉伸训练": "低",
    "活动度训练": "低",
    "等长收缩": "低",
    "核心控制": "低",
    "核心稳定": "中",
    "力量训练": "中",
}

EQUIPMENT_BY_ID = {
    "wall_squat": ["墙面"],
    "shoulder_external_rotation": ["弹力带"],
    "quad_set": ["毛巾卷"],
    "calf_stretch": ["墙面"],
}


def _as_list(value):
    if isinstance(value, list):
        return value
    return []


def _region_muscles(regions: list[str]) -> list[str]:
    muscles = []
    for region in regions:
        for item in MUSCLES_BY_REGION.get(region, []):
            if item not in muscles:
                muscles.append(item)
    return muscles


def _default_steps(action_name: str) -> list[str]:
    return [
        f"准备姿势：按示范进入 {action_name} 起始位置，保持呼吸自然。",
        "执行动作：缓慢完成动作，避免突然用力或借力代偿。",
        "结束还原：回到起始位置，观察疼痛、麻木或不适变化。",
    ]


def _default_mistakes(category: str) -> list[str]:
    if category == "力量训练":
        return ["速度过快", "用疼痛部位代偿发力", "动作幅度超过无痛范围"]
    if category == "拉伸训练":
        return ["拉伸到疼痛明显加重", "憋气", "身体旋转代偿"]
    if category in {"核心稳定", "核心控制"}:
        return ["腰背塌陷", "骨盆左右晃动", "只追求幅度忽视控制"]
    return ["动作过快", "未保持中立姿势", "出现不适仍继续训练"]


def _default_cues(category: str) -> list[str]:
    if category == "力量训练":
        return ["慢起慢落", "保持关节对线", "以轻微疲劳但不疼痛为准"]
    if category == "拉伸训练":
        return ["保持轻微牵拉感", "不要弹震", "配合缓慢呼吸"]
    if category in {"核心稳定", "核心控制"}:
        return ["收紧下腹", "保持躯干稳定", "动作宁小勿乱"]
    return ["动作缓慢可控", "保持自然呼吸", "出现疼痛加重立即停止"]


def enrich_action_payload(payload: dict) -> dict:
    action = dict(payload)
    action_id = action.get("id") or "exercise_generic"
    regions = _as_list(action.get("body_regions"))
    category = action.get("category") or CATEGORY_BY_ID.get(action_id) or "康复训练"
    difficulty = action.get("difficulty_level") or DIFFICULTY_BY_CATEGORY.get(category) or "初级"
    image = action.get("image") or f"assets/actions/{action_id}.png"
    video_url = action.get("video_url") or ""

    action.setdefault("category", category)
    action.setdefault("difficulty_level", difficulty)
    action.setdefault("stage", STAGE_BY_CATEGORY.get(category, "基础恢复期"))
    action.setdefault("target_muscles", _region_muscles(regions))
    action.setdefault("equipment", EQUIPMENT_BY_ID.get(action_id, ["徒手"]))
    action.setdefault("image", image)
    action.setdefault("video_url", video_url)
    action.setdefault("video_hint", f"可搜索：{action.get('name') or action_id} 康复训练 示范")
    action.setdefault("image_hint", "建议使用正面或侧面分步示意图，标出关键关节对线和动作方向。")
    action.setdefault("steps", _default_steps(action.get("name") or action_id))
    action.setdefault("common_mistakes", _default_mistakes(category))
    action.setdefault("correct_cues", _default_cues(category))
    action.setdefault("risk_level", RISK_BY_CATEGORY.get(category, "低"))
    action.setdefault("demo_media", {
        "image": image,
        "video": video_url,
        "video_hint": action.get("video_hint"),
        "image_hint": action.get("image_hint"),
    })
    return action
