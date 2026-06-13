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
