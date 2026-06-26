from __future__ import annotations

import json
from typing import Any

from .knowledge import REGION_HINTS, load_action_library, select_actions_for_request


PREVENTION_TIPS = {
    "颈部": [
        "减少长时间低头，每 30-45 分钟进行一次颈肩放松。",
        "屏幕高度尽量与视线平齐，避免头前伸姿势。",
        "睡眠枕头以支撑颈椎自然曲度为宜。",
    ],
    "肩部": [
        "避免突然大幅度抬举重物，先恢复肩胛控制。",
        "久坐办公时保持肩部放松，减少耸肩。",
        "肩痛明显时优先做小幅度活动度练习。",
    ],
    "腰部": [
        "久坐时每 30-45 分钟起身活动，避免持续弯腰。",
        "搬物时靠近身体并屈髋屈膝，减少腰椎剪切压力。",
        "核心训练应从低负荷、可控动作开始。",
    ],
    "膝关节": [
        "上下楼和下蹲时保持膝盖朝向脚尖。",
        "疼痛期减少跑跳和深蹲，优先恢复股四头肌控制。",
        "训练后若肿胀增加，应降低强度并观察。",
    ],
    "踝关节": [
        "急性扭伤早期避免强行拉伸，先控制肿胀。",
        "恢复期逐步加入踝泵、提踵和平衡训练。",
        "运动前做好小腿和踝关节热身。",
    ],
}

REGION_ARTICLE_SUMMARY = {
    "颈部": "颈部康复重点是减少头前伸负荷、恢复深层颈屈肌控制和肩颈协同。",
    "肩部": "肩部康复重点是恢复肩胛稳定、肩关节活动度和旋袖肌群控制。",
    "腰部": "腰部康复重点是控制疼痛诱因、恢复核心稳定和髋腰协同发力。",
    "膝关节": "膝关节康复重点是改善疼痛、恢复股四头肌力量和下肢对线控制。",
    "踝关节": "踝关节康复重点是恢复活动度、控制肿胀并逐步恢复负重和平衡能力。",
}


def _action_payload(action) -> dict[str, Any]:
    return action.model_dump() if hasattr(action, "model_dump") else action.dict()


def infer_regions(text: str, explicit_regions: list[str] | None = None) -> list[str]:
    query = (text or "").lower()
    regions = list(explicit_regions or [])
    for region, hints in REGION_HINTS.items():
        if region not in regions and any(hint.lower() in query for hint in hints):
            regions.append(region)
    return regions


def build_knowledge_articles(
    q: str | None = None,
    body_region: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    actions = load_action_library()
    query = (q or "").lower()
    requested_regions = [body_region] if body_region else infer_regions(query)
    if not requested_regions:
        requested_regions = list(REGION_ARTICLE_SUMMARY)

    articles = []
    for region in requested_regions:
        related_actions = [
            action for action in actions
            if region in (action.body_regions or [])
            and (not query or query in action.name.lower() or any(query in item.lower() for item in action.target_conditions or []))
        ]
        if not related_actions:
            related_actions = [action for action in actions if region in (action.body_regions or [])]
        summary = REGION_ARTICLE_SUMMARY.get(region, f"{region}康复应遵循循序渐进、疼痛可控和动作标准原则。")
        action_names = "、".join(action.name for action in related_actions[:4]) or "基础活动度训练"
        articles.append({
            "id": f"region_{region}",
            "title": f"{region}康复与预防建议",
            "category": "康复百科",
            "body_regions": [region],
            "summary": summary,
            "content": (
                f"{summary} 可结合 {action_names} 等低风险训练建立基础能力。"
                "训练过程中应以疼痛不明显加重为原则，并根据活动度、完成率和动作评分逐步调整。"
            ),
            "related_actions": [_action_payload(action) for action in related_actions[:4]],
            "prevention_tips": PREVENTION_TIPS.get(region, ["保持规律活动，避免突然增加训练量。"]),
        })
    return articles[: max(1, min(limit, 30))]


def _format_rag_contexts(rag_contexts: list[dict[str, Any]]) -> str:
    if not rag_contexts:
        return "暂无额外检索上下文。"
    lines = []
    for index, item in enumerate(rag_contexts[:5], start=1):
        metadata = item.get("metadata") or {}
        title = metadata.get("title") or item.get("id") or f"资料{index}"
        text = (item.get("text") or "").strip()
        if text:
            lines.append(f"[{index}] {title}: {text[:700]}")
    return "\n".join(lines) or "暂无额外检索上下文。"


def _build_knowledge_answer_prompt(
    question: str,
    regions: list[str],
    articles: list[dict[str, Any]],
    suggested_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
    safety_notes: list[str],
) -> str:
    action_payload = [_action_payload(action) for action in suggested_actions[:5]]
    article_payload = [
        {
            "title": article.get("title"),
            "summary": article.get("summary"),
            "content": article.get("content"),
            "prevention_tips": article.get("prevention_tips"),
        }
        for article in articles[:3]
    ]
    return f"""你是中文运动康复科普问答助手。请基于给定资料回答用户问题，要求：
1. 第一段必须正面回答用户的具体问题，不要只泛泛介绍部位康复原则。
2. 说明可以做什么、暂时避免什么、如何判断是否需要降级或就医。
3. 只给科普建议，不替代医生诊断；不要编造资料中没有的动作或医学结论。
4. 用自然中文输出，控制在 250-450 字，分 3-5 个短段落或要点。

用户问题：
{question}

关联部位：
{", ".join(regions) if regions else "未明确"}

本地文章摘要：
{json.dumps(article_payload, ensure_ascii=False, indent=2)}

可参考动作：
{json.dumps(action_payload, ensure_ascii=False, indent=2)}

RAG 检索上下文：
{_format_rag_contexts(rag_contexts)}

必须保留的安全提醒：
{json.dumps(safety_notes, ensure_ascii=False, indent=2)}
"""


def _fallback_knowledge_answer(
    regions: list[str],
    articles: list[dict[str, Any]],
    suggested_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
) -> str:
    article_text = "；".join(article["summary"] for article in articles[:2])
    action_text = "、".join(action.name for action in suggested_actions[:3]) or "基础活动度训练"
    region_text = "、".join(regions) if regions else "相关部位"
    context_text = ""
    if rag_contexts:
        context_text = " 检索到的康复知识提示：" + "；".join(
            item.get("text", "")[:120] for item in rag_contexts[:2]
        )
    return (
        f"根据本地康复知识库，你的问题主要关联 {region_text}。{article_text}"
        f"{context_text} 可优先参考 {action_text}，从低强度开始，训练前后记录 VAS 疼痛评分和完成情况。"
    )


def _generate_knowledge_answer(
    question: str,
    regions: list[str],
    articles: list[dict[str, Any]],
    suggested_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
    safety_notes: list[str],
) -> str:
    from .doubao import generate_summary

    prompt = _build_knowledge_answer_prompt(
        question=question,
        regions=regions,
        articles=articles,
        suggested_actions=suggested_actions,
        rag_contexts=rag_contexts,
        safety_notes=safety_notes,
    )
    result = generate_summary(prompt)
    answer = (result.get("text") or "").strip() if isinstance(result, dict) else ""
    if not answer:
        raise RuntimeError("DeepSeek returned empty answer")
    return answer


def answer_knowledge_question(question: str, pain_regions: list[str] | None = None, limit: int = 4) -> dict[str, Any]:
    if not question or not question.strip():
        raise ValueError("question required")
    normalized_limit = max(1, min(limit or 4, 8))
    regions = infer_regions(question, pain_regions)
    articles = build_knowledge_articles(q=question, body_region=regions[0] if len(regions) == 1 else None, limit=normalized_limit)
    suggested_actions = select_actions_for_request(
        symptoms=question,
        pain_regions=regions,
        limit=normalized_limit,
    )
    try:
        from .rag import retrieve_contexts

        rag_contexts = retrieve_contexts(
            query=question,
            limit=normalized_limit,
            body_regions=regions or None,
        )
    except Exception:
        rag_contexts = []
    safety_notes = [
        "若出现剧烈疼痛、麻木无力、大小便异常、发热或症状快速加重，请停止训练并及时就医。",
        "科普问答不能替代医生诊断，具体训练强度需结合个人病情调整。",
    ]
    try:
        answer = _generate_knowledge_answer(
            question=question,
            regions=regions,
            articles=articles,
            suggested_actions=suggested_actions,
            rag_contexts=rag_contexts,
            safety_notes=safety_notes,
        )
    except Exception:
        answer = _fallback_knowledge_answer(
            regions=regions,
            articles=articles,
            suggested_actions=suggested_actions,
            rag_contexts=rag_contexts,
        )
    return {
        "answer": answer,
        "references": articles,
        "suggested_actions": [_action_payload(action) for action in suggested_actions],
        "safety_notes": safety_notes,
        "rag_contexts": rag_contexts,
    }
