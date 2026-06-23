import re
from typing import List, Optional

_MEDICAL_HINTS = (
    "痛", "疼", "酸", "胀", "麻", "受限", "不适", "僵硬", "无力",
    "肿胀", "损伤", "劳损", "突出", "扭伤", "康复", "活动", "弯曲",
    "拉伸", "久坐", "炎症", "术后", "复发", "疲劳", "劳累", "受伤",
    "拉伤", "挫伤", "骨折", "压迫", "抽搐", "痉挛", "水肿",
)

_BODY_PART_HINTS = (
    "颈", "脖子", "肩", "肩膀", "腰", "背", "后背", "膝", "膝盖",
    "踝", "肘", "腕", "髋", "腿", "足", "头", "胸", "肌", "关节", "椎",
    "肩周", "腰椎", "颈椎", "胸椎", "髌", "跟腱", "足底", "手臂", "小腿",
    "大腿", "肩胛",
)

_RED_FLAG_RULES = (
    {
        "code": "severe_pain",
        "label": "剧烈疼痛",
        "patterns": (
            r"剧烈疼痛",
            r"疼痛难忍",
            r"痛到无法",
            r"无法忍受",
            r"夜间痛醒",
            r"静息痛",
        ),
    },
    {
        "code": "numbness_or_weakness",
        "label": "麻木或无力",
        "patterns": (
            r"麻木",
            r"无力",
            r"乏力",
            r"肌力下降",
            r"拿不稳",
            r"走路不稳",
            r"脚下踩棉",
            r"感觉减退",
        ),
    },
    {
        "code": "bowel_bladder_abnormality",
        "label": "大小便异常",
        "patterns": (
            r"大小便异常",
            r"大小便失禁",
            r"尿失禁",
            r"尿潴留",
            r"排尿困难",
            r"排便困难",
            r"会阴麻木",
            r"鞍区麻木",
        ),
    },
    {
        "code": "trauma_related",
        "label": "外伤后疼痛",
        "patterns": (
            r"外伤",
            r"摔倒",
            r"跌倒",
            r"撞伤",
            r"车祸",
            r"扭伤后",
            r"骨折",
        ),
    },
    {
        "code": "fever_or_infection",
        "label": "发热或感染风险",
        "patterns": (
            r"发热",
            r"发烧",
            r"高烧",
            r"寒战",
            r"感染",
            r"红肿热痛",
        ),
    },
    {
        "code": "rapid_worsening",
        "label": "症状快速加重",
        "patterns": (
            r"快速加重",
            r"突然加重",
            r"明显加重",
            r"持续加重",
            r"越来越重",
            r"进行性加重",
        ),
    },
    {
        "code": "unexplained_weight_loss",
        "label": "不明原因体重下降",
        "patterns": (
            r"体重骤降",
            r"体重明显下降",
            r"不明原因消瘦",
            r"不明原因体重下降",
        ),
    },
)


def _is_rehab_related(text: str) -> bool:
    if any(hint in text for hint in _MEDICAL_HINTS):
        return True
    if any(hint in text for hint in _BODY_PART_HINTS):
        return True
    return False


def validate_pain_regions(pain_regions: Optional[List[str]]) -> str | None:
    if not pain_regions:
        return "请至少选择一个疼痛部位"
    return None


def validate_symptoms(symptoms: str, pain_regions: Optional[List[str]] = None) -> str | None:
    text = symptoms.strip()
    if not text:
        return "请填写主诉信息"
    if len(text) < 4:
        return "主诉描述过短，请至少用一句话说明症状与部位"
    if re.fullmatch(r"\d+", text):
        return "主诉不能使用纯数字，请描述具体疼痛或活动受限情况"
    if re.fullmatch(r"[a-zA-Z]+", text):
        return "请使用中文描述症状，例如：颈部疼痛两周，转头受限"
    if re.search(r"(.)\1{5,}", text):
        return "主诉内容重复异常，请填写真实的伤病描述"

    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if chinese_count < 1:
        return "主诉信息不明确，请描述具体症状与持续时间，例如：腰痛一月，弯腰加重"

    if not _is_rehab_related(text):
        return (
            "主诉内容与康复伤病描述不符，请用规范语言描述具体症状，"
            "例如：腰部酸痛一月，久坐后加重"
        )

    return None


def detect_red_flags(symptoms: str, history: Optional[str] = None) -> list[dict]:
    text = " ".join(part.strip() for part in (symptoms, history or "") if part and part.strip())
    if not text:
        return []

    matches = []
    for rule in _RED_FLAG_RULES:
        matched_patterns = [
            pattern
            for pattern in rule["patterns"]
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]
        if matched_patterns:
            matches.append({
                "code": rule["code"],
                "label": rule["label"],
                "matched": matched_patterns,
            })
    return matches


def red_flag_error_message(red_flags: list[dict]) -> str:
    labels = "、".join(item["label"] for item in red_flags)
    return (
        f"检测到红旗症状：{labels}。为避免延误病情，系统已暂停生成普通居家康复训练处方，"
        "请尽快前往医院或咨询专业医生/康复治疗师。"
    )
