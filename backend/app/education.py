from __future__ import annotations

import json
import hashlib
from typing import Any

from .knowledge import REGION_HINTS, load_action_library, select_actions_for_request
from .validators import detect_red_flags


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

REGION_DO_AND_AVOID = {
    "颈部": {
        "do": ["优先做下巴回收、轻柔活动度和肩胛控制训练。", "办公时把屏幕抬高到接近视线水平。"],
        "avoid": ["避免快速甩头、长时间低头和疼痛明显的强拉伸。"],
    },
    "肩部": {
        "do": ["优先恢复肩胛稳定和小范围无痛活动。", "训练时保持肩部放松，避免耸肩代偿。"],
        "avoid": ["避免突然大幅度抬举、负重推举和诱发夜间痛的动作。"],
    },
    "腰部": {
        "do": ["优先做骨盆控制、核心稳定和髋部协同训练。", "久坐后先起身走动，再做低负荷练习。"],
        "avoid": ["避免急性疼痛期反复弯腰搬重物、强行拉伸或憋气发力。"],
    },
    "膝关节": {
        "do": ["优先恢复股四头肌控制、髋膝踝对线和小角度力量。", "上下楼时注意膝盖方向与脚尖一致。"],
        "avoid": ["避免疼痛期跑跳、深蹲到底和膝盖内扣。"],
    },
    "踝关节": {
        "do": ["恢复期逐步做踝泵、提踵和平衡训练。", "运动前做好小腿和踝关节热身。"],
        "avoid": ["急性扭伤早期避免强行牵拉、带痛负重和快速变向。"],
    },
}

BODY_REGION_ALIASES = {
    "颈部": ["颈部", "颈椎", "脖子", "脖", "落枕"],
    "肩部": ["肩部", "肩膀", "肩", "肩胛", "肩周"],
    "腰部": ["腰部", "腰", "腰椎", "腰背", "腰肌", "坐骨"],
    "膝关节": ["膝关节", "膝盖", "膝", "髌骨"],
    "踝关节": ["踝关节", "脚踝", "踝", "跟腱", "小腿"],
    "髋部": ["髋部", "髋", "臀部", "臀"],
    "腕部": ["腕部", "手腕", "腕"],
    "肘部": ["肘部", "手肘", "肘"],
    "背部": ["背部", "后背", "上背"],
    "胸部": ["胸部", "胸"],
    "足部": ["足部", "脚底", "足底", "脚掌"],
}


def _query_terms(text: str) -> list[str]:
    query = (text or "").lower()
    terms = [query] if query else []
    for hints in REGION_HINTS.values():
        terms.extend(hint.lower() for hint in hints if hint and hint.lower() in query)
    terms.extend(token for token in ["疼痛", "酸痛", "僵硬", "麻木", "无力", "肿胀", "久坐", "活动受限"] if token in query)
    return [term for term in terms if term]


def _action_payload(action) -> dict[str, Any]:
    return action.model_dump() if hasattr(action, "model_dump") else action.dict()


def _supported_body_regions() -> set[str]:
    supported: set[str] = set()
    for action in load_action_library():
        supported.update(action.body_regions or [])
    return supported


def _canonical_region(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for region, aliases in BODY_REGION_ALIASES.items():
        if text == region or text in aliases:
            return region
    return text


def _detect_requested_regions(text: str, explicit_regions: list[str] | None = None) -> list[str]:
    query = (text or "").lower()
    regions = []
    for region in explicit_regions or []:
        canonical = _canonical_region(region)
        if canonical and canonical not in regions:
            regions.append(canonical)
    for region, aliases in BODY_REGION_ALIASES.items():
        if region not in regions and any(alias.lower() in query for alias in aliases):
            regions.append(region)
    for region in infer_regions(text):
        canonical = _canonical_region(region)
        if canonical and canonical not in regions:
            regions.append(canonical)
    return regions


def _coverage_info(requested_regions: list[str]) -> dict[str, Any]:
    supported = _supported_body_regions()
    supported_regions = [region for region in requested_regions if region in supported]
    unsupported_regions = [region for region in requested_regions if region not in supported]
    if unsupported_regions and supported_regions:
        status = "partial"
        message = (
            f"当前动作库已覆盖 {'、'.join(supported_regions)}，暂未覆盖 {'、'.join(unsupported_regions)}。"
            "系统只会基于已覆盖部位推荐动作，未覆盖部位仅提供通用安全科普。"
        )
    elif unsupported_regions:
        status = "unsupported_region"
        message = (
            f"当前动作库暂未覆盖 {'、'.join(unsupported_regions)}。"
            "本次不推荐具体训练动作，仅提供通用安全科普和就医提醒。"
        )
    else:
        status = "supported" if supported_regions else "unknown"
        message = None if supported_regions else "未识别到明确疼痛部位，将提供通用康复科普建议。"
    return {
        "coverage_status": status,
        "supported_regions": supported_regions,
        "unsupported_regions": unsupported_regions,
        "coverage_message": message,
    }


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

    query_terms = _query_terms(query)
    articles = []
    for region in requested_regions:
        related_actions = [
            action for action in actions
            if region in (action.body_regions or [])
            and (
                not query_terms
                or any(term in action.name.lower() for term in query_terms)
                or any(term in (action.description or "").lower() for term in query_terms)
                or any(
                    term in item.lower()
                    for item in action.target_conditions or []
                    for term in query_terms
                )
            )
        ]
        if not related_actions:
            related_actions = [action for action in actions if region in (action.body_regions or [])]
        summary = REGION_ARTICLE_SUMMARY.get(region, f"{region}康复应遵循循序渐进、疼痛可控和动作标准原则。")
        advice = REGION_DO_AND_AVOID.get(region, {"do": [], "avoid": []})
        action_names = "、".join(action.name for action in related_actions[:4]) or "基础活动度训练"
        articles.append({
            "id": f"region_{region}",
            "title": f"{region}康复与预防建议",
            "category": "康复百科",
            "body_regions": [region],
            "summary": summary,
            "content": (
                f"{summary} 可结合 {action_names} 等低风险训练建立基础能力。"
                f"建议：{'；'.join(advice.get('do') or [])} "
                f"暂时避免：{'；'.join(advice.get('avoid') or [])} "
                "训练过程中应以疼痛不明显加重为原则，并根据活动度、完成率和动作评分逐步调整。"
                "若出现剧烈疼痛、麻木无力、大小便异常、发热或症状快速加重，应停止训练并就医。"
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
    question: str,
    regions: list[str],
    articles: list[dict[str, Any]],
    suggested_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
    safety_notes: list[str],
    coverage: dict[str, Any] | None = None,
) -> str:
    coverage = coverage or {}
    article_text = "；".join(article["summary"] for article in articles[:2])
    action_text = "、".join(action.name for action in suggested_actions[:3]) or "基础活动度训练"
    region_text = "、".join(regions) if regions else "相关部位"
    red_flags = detect_red_flags(question)
    if red_flags:
        labels = "、".join(item["label"] for item in red_flags)
        return (
            f"你的问题中出现了 {labels} 等需要警惕的信号。此时不建议直接按普通居家训练处理，"
            "应先停止诱发症状的动作，并尽快咨询医生或康复治疗师，排除神经受压、感染、外伤等风险。\n\n"
            "在专业评估前，可做的主要是避免加重刺激、记录疼痛部位和变化、准备既往检查资料；"
            "暂时避免负重、快速扭转、强拉伸和带痛训练。\n\n"
            f"{safety_notes[0]}"
        )

    if coverage.get("coverage_status") == "unsupported_region":
        unsupported_text = "、".join(coverage.get("unsupported_regions") or []) or region_text
        return (
            f"当前动作库暂未覆盖 {unsupported_text}，因此不建议系统强行推荐具体训练动作。"
            "可以先采用通用处理原则：减少诱发疼痛的活动，避免带痛负重、快速扭转和强拉伸，"
            "记录疼痛部位、持续时间、肿胀或麻木等变化。\n\n"
            "若只是轻度不适，可在无痛范围内做轻柔活动和日常姿势调整；如果疼痛持续、影响功能，"
            "建议由医生或康复治疗师评估后再制定训练方案。\n\n"
            f"{safety_notes[0]}"
        )

    context_text = ""
    if rag_contexts:
        context_text = " 检索到的康复知识提示：" + "；".join(
            item.get("text", "")[:120] for item in rag_contexts[:2]
        )
    action_details = []
    for action in suggested_actions[:3]:
        detail = f"{action.name}（{action.sets}组×{action.reps}次"
        if action.frequency:
            detail += f"，{action.frequency}"
        detail += "）"
        action_details.append(detail)
    action_detail_text = "、".join(action_details) or action_text
    avoidance = []
    for region in regions:
        avoidance.extend(REGION_DO_AND_AVOID.get(region, {}).get("avoid") or [])
    avoid_text = "；".join(dict.fromkeys(avoidance)) or "避免疼痛明显加重的动作、突然增加训练量和带痛硬撑。"
    return (
        f"根据本地康复知识库，你的问题主要关联 {region_text}。{article_text}{context_text}\n\n"
        f"可以优先从低强度动作开始，例如 {action_detail_text}。训练时保持动作慢、幅度可控，"
        "以训练中和训练后疼痛不明显增加为原则，并记录 VAS 疼痛评分、完成组数和动作评分。\n\n"
        f"暂时避免：{avoid_text} 如果某个动作让疼痛上升 2 分以上、出现麻木无力或第二天明显加重，"
        "应先降阶为更小幅度、更少组数，或暂停该动作。\n\n"
        f"{safety_notes[0]}"
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
    requested_regions = _detect_requested_regions(question, pain_regions)
    coverage = _coverage_info(requested_regions)
    regions = coverage["supported_regions"] or requested_regions
    article_region = regions[0] if len(regions) == 1 else None
    articles = build_knowledge_articles(q=question, body_region=article_region, limit=normalized_limit)
    if coverage["coverage_status"] == "unsupported_region":
        suggested_actions = []
    else:
        suggested_actions = select_actions_for_request(
            symptoms=question,
            pain_regions=coverage["supported_regions"] or regions,
            limit=normalized_limit,
        )
    try:
        from .rag import retrieve_contexts

        if coverage["coverage_status"] == "unsupported_region":
            rag_contexts = []
        else:
            rag_contexts = retrieve_contexts(
                query=question,
                limit=normalized_limit,
                body_regions=coverage["supported_regions"] or regions or None,
                kind="action",
            )
            rag_contexts = [
                item for item in rag_contexts
                if (item.get("metadata") or {}).get("kind") == "action"
            ]
    except Exception:
        rag_contexts = []
    safety_notes = [
        "若出现剧烈疼痛、麻木无力、大小便异常、发热或症状快速加重，请停止训练并及时就医。",
        "科普问答不能替代医生诊断，具体训练强度需结合个人病情调整。",
    ]
    if coverage["coverage_status"] == "unsupported_region":
        answer = _fallback_knowledge_answer(
            question=question,
            regions=regions,
            articles=articles,
            suggested_actions=suggested_actions,
            rag_contexts=rag_contexts,
            safety_notes=safety_notes,
            coverage=coverage,
        )
    else:
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
                question=question,
                regions=regions,
                articles=articles,
                suggested_actions=suggested_actions,
                rag_contexts=rag_contexts,
                safety_notes=safety_notes,
                coverage=coverage,
            )
    return {
        "answer": answer,
        "references": articles,
        "suggested_actions": [_action_payload(action) for action in suggested_actions],
        "safety_notes": safety_notes,
        "rag_contexts": rag_contexts,
        "coverage_status": coverage["coverage_status"],
        "unsupported_regions": coverage["unsupported_regions"],
        "coverage_message": coverage["coverage_message"],
    }


ARTICLE_TYPE_LABELS = {
    "region": "部位康复百科",
    "question": "问题型康复科普",
    "action": "动作讲解科普",
}


def _find_action(action_id: str | None = None, query: str | None = None):
    actions = load_action_library()
    lookup = (action_id or "").strip()
    if lookup:
        for action in actions:
            if action.id == lookup:
                return action
    query_text = (query or "").strip().lower()
    if query_text:
        for action in actions:
            if query_text in action.name.lower() or (action.id and query_text in action.id.lower()):
                return action
    return None


def _article_sections_to_content(sections: list[dict[str, str]]) -> str:
    return "\n\n".join(
        f"## {section.get('heading', '').strip()}\n{section.get('content', '').strip()}"
        for section in sections
        if section.get("heading") and section.get("content")
    )


def _generated_article_id(article_type: str, query: str) -> str:
    digest = hashlib.sha1(f"{article_type}:{query}".encode("utf-8")).hexdigest()[:12]
    return f"generated_{article_type}_{digest}"


def _normalize_generated_article_payload(
    payload: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    title = str(payload.get("title") or fallback["title"]).strip()
    summary = str(payload.get("summary") or fallback["summary"]).strip()
    raw_sections = payload.get("sections")
    sections = []
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if not isinstance(item, dict):
                continue
            heading = str(item.get("heading") or item.get("title") or "").strip()
            content = str(item.get("content") or item.get("body") or "").strip()
            if heading and content:
                sections.append({"heading": heading, "content": content})
    if not sections:
        sections = fallback["sections"]
    return {
        **fallback,
        "title": title,
        "summary": summary,
        "sections": sections,
        "content": _article_sections_to_content(sections),
        "generated_by": "model",
    }


def _fallback_generated_article(
    article_type: str,
    query: str,
    regions: list[str],
    related_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
    safety_notes: list[str],
    red_flags: list[dict],
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = coverage or {}
    region_text = "、".join(regions) if regions else "相关部位"
    action_payload = [_action_payload(action) for action in related_actions[:4]]
    action_text = "、".join(action.name for action in related_actions[:4]) or "低强度活动度训练"
    if red_flags:
        labels = "、".join(item["label"] for item in red_flags)
        title = f"{region_text}红旗症状与就医提醒" if regions else "康复训练前的就医提醒"
        summary = f"问题中出现 {labels}，不建议直接进入普通居家康复训练，应先进行专业评估。"
        sections = [
            {
                "heading": "为什么需要警惕",
                "content": f"{labels} 可能提示神经受压、感染、外伤后损伤或其他需要医生判断的情况，普通训练可能延误处理。",
            },
            {
                "heading": "现在可以做什么",
                "content": "先停止诱发症状的动作，记录疼痛部位、持续时间、麻木或无力范围，并准备既往影像报告和用药信息。",
            },
            {
                "heading": "暂时避免什么",
                "content": "避免负重训练、快速扭转、强拉伸、深蹲跑跳和任何带痛硬撑的动作。",
            },
            {
                "heading": "何时就医",
                "content": safety_notes[0],
            },
        ]
        return {
            "id": _generated_article_id(article_type, query),
            "article_type": article_type,
            "title": title,
            "category": "就医提醒型科普",
            "body_regions": regions,
            "summary": summary,
            "sections": sections,
            "content": _article_sections_to_content(sections),
            "related_actions": [],
            "prevention_tips": [],
            "safety_notes": safety_notes,
            "rag_contexts": rag_contexts,
            "generated_by": "fallback",
            "coverage_status": coverage.get("coverage_status"),
            "unsupported_regions": coverage.get("unsupported_regions") or [],
            "coverage_message": coverage.get("coverage_message"),
        }

    if coverage.get("coverage_status") == "unsupported_region":
        unsupported_text = "、".join(coverage.get("unsupported_regions") or []) or region_text
        title = f"{unsupported_text}通用康复科普与就医提醒"
        summary = f"当前动作库暂未覆盖 {unsupported_text}，本篇仅提供通用安全科普，不推荐具体训练动作。"
        sections = [
            {
                "heading": "覆盖范围说明",
                "content": coverage.get("coverage_message") or summary,
            },
            {
                "heading": "可以先做什么",
                "content": "减少诱发疼痛的活动，记录疼痛部位、持续时间、是否肿胀、麻木或无力，并保持日常轻柔活动。",
            },
            {
                "heading": "暂时避免什么",
                "content": "避免带痛负重、快速扭转、强拉伸、反复冲击和任何让症状明显加重的训练。",
            },
            {
                "heading": "如何判断需要专业评估",
                "content": "若疼痛持续不缓解、影响日常功能、伴随肿胀麻木无力，或不清楚损伤原因，应先咨询医生或康复治疗师。",
            },
            {
                "heading": "何时就医",
                "content": safety_notes[0],
            },
        ]
        return {
            "id": _generated_article_id(article_type, query),
            "article_type": article_type,
            "title": title,
            "category": "未覆盖部位通用科普",
            "body_regions": regions,
            "summary": summary,
            "sections": sections,
            "content": _article_sections_to_content(sections),
            "related_actions": [],
            "prevention_tips": [],
            "safety_notes": safety_notes,
            "rag_contexts": [],
            "generated_by": "fallback",
            "coverage_status": coverage.get("coverage_status"),
            "unsupported_regions": coverage.get("unsupported_regions") or [],
            "coverage_message": coverage.get("coverage_message"),
        }

    if article_type == "action" and related_actions:
        action = related_actions[0]
        title = f"{action.name}动作讲解与安全要点"
        summary = f"{action.name}适用于{region_text}相关康复训练，应在疼痛可控范围内完成。"
        sections = [
            {"heading": "适合什么情况", "content": "、".join(action.target_conditions or []) or f"{region_text}活动受限或力量控制不足。"},
            {"heading": "怎么做", "content": action.description or "保持动作缓慢、稳定，避免突然发力。"},
            {"heading": "推荐剂量", "content": f"可参考 {action.sets} 组×{action.reps} 次，{action.frequency or '按个人耐受频次'}。"},
            {"heading": "暂时避免", "content": action.contraindications or "训练中疼痛明显增加时暂停。"},
            {"heading": "进阶与降阶", "content": f"进阶：{action.progression or '无痛稳定后再增加强度'} 降阶：{action.regression or '减少幅度、组数或保持时间'}"},
        ]
    else:
        title = f"{region_text}康复与预防建议" if article_type == "region" else f"{query or region_text}康复科普建议"
        summary = f"{region_text}康复重点是疼痛可控、循序渐进、动作标准，并结合个人反馈调整。"
        sections = [
            {"heading": "问题概述", "content": f"当前问题主要关联 {region_text}。康复训练应先控制诱因，再恢复活动度、力量和动作控制。"},
            {"heading": "可以做什么", "content": f"可优先参考 {action_text}，从低强度、少组数开始，训练前后记录疼痛变化。"},
            {"heading": "暂时避免什么", "content": "避免疼痛明显加重的动作、突然增加训练量、憋气发力和带痛硬撑。"},
            {"heading": "如何降级", "content": "若训练中疼痛上升 2 分以上或第二天明显加重，应减少幅度、组数或改为更基础动作。"},
            {"heading": "何时就医", "content": safety_notes[0]},
        ]

    return {
        "id": _generated_article_id(article_type, query or region_text),
        "article_type": article_type,
        "title": title,
        "category": ARTICLE_TYPE_LABELS.get(article_type, "康复科普"),
        "body_regions": regions,
        "summary": summary,
        "sections": sections,
        "content": _article_sections_to_content(sections),
        "related_actions": action_payload,
        "prevention_tips": [tip for region in regions for tip in PREVENTION_TIPS.get(region, [])],
        "safety_notes": safety_notes,
        "rag_contexts": rag_contexts,
        "generated_by": "fallback",
        "coverage_status": coverage.get("coverage_status"),
        "unsupported_regions": coverage.get("unsupported_regions") or [],
        "coverage_message": coverage.get("coverage_message"),
    }


def _build_generated_article_prompt(
    article_type: str,
    query: str,
    regions: list[str],
    related_actions: list[Any],
    rag_contexts: list[dict[str, Any]],
    safety_notes: list[str],
    red_flags: list[dict],
    coverage: dict[str, Any] | None = None,
) -> str:
    action_payload = [_action_payload(action) for action in related_actions[:5]]
    red_flag_text = json.dumps(red_flags, ensure_ascii=False, indent=2) if red_flags else "[]"
    article_mode = "就医提醒型科普" if red_flags else ARTICLE_TYPE_LABELS.get(article_type, "康复科普")
    coverage = coverage or {}
    return f"""你是中文运动康复科普文章编辑。请基于 RAG 检索资料和动作库生成一篇结构化 JSON 科普文章。

文章类型：{article_type}
文章模式：{article_mode}
用户问题或主题：{query}
关联部位：{", ".join(regions) if regions else "未明确"}
红旗症状：{red_flag_text}
动作库覆盖状态：{coverage.get("coverage_status") or "unknown"}
未覆盖部位：{"、".join(coverage.get("unsupported_regions") or []) or "无"}
覆盖说明：{coverage.get("coverage_message") or "无"}

RAG 检索上下文：
{_format_rag_contexts(rag_contexts)}

可引用动作库动作：
{json.dumps(action_payload, ensure_ascii=False, indent=2)}

安全提醒：
{json.dumps(safety_notes, ensure_ascii=False, indent=2)}

输出要求：
1. 只输出 JSON 对象，不要 Markdown 代码块。
2. 字段必须包含 title、summary、sections。
3. sections 是数组，每项包含 heading 和 content。
4. 若存在红旗症状，必须生成“就医提醒型科普”，不要推荐具体训练动作，只说明为什么要警惕、现在可以做什么、暂时避免什么、何时就医。
5. 若无红旗症状，文章必须包含：问题概述、可以做什么、暂时避免什么、推荐动作、如何降级、何时就医。
6. 如果动作库覆盖状态为 unsupported_region，不要推荐任何具体动作，只输出通用安全科普和就医提醒。
7. 不要编造动作库和 RAG 上下文之外的动作或医学结论；不要替代医生诊断。
"""


def generate_knowledge_article_with_rag(
    article_type: str = "question",
    query: str | None = None,
    body_region: str | None = None,
    action_id: str | None = None,
    pain_regions: list[str] | None = None,
    limit: int = 4,
) -> dict[str, Any]:
    normalized_type = (article_type or "question").strip().lower()
    if normalized_type not in ARTICLE_TYPE_LABELS:
        raise ValueError("article_type must be one of: region, question, action")

    normalized_limit = max(1, min(limit or 4, 8))
    target_action = _find_action(action_id=action_id, query=query) if normalized_type == "action" else None
    if normalized_type == "action" and not target_action:
        raise ValueError("action_id or query must match an existing action")

    base_query = (query or "").strip()
    if normalized_type == "region":
        if not body_region and pain_regions:
            body_region = pain_regions[0]
        if not body_region:
            raise ValueError("body_region required for region article")
        base_query = base_query or f"{body_region}康复与预防建议"
    elif normalized_type == "question":
        if not base_query:
            raise ValueError("query required for question article")
    elif target_action:
        base_query = base_query or target_action.name

    explicit_regions = list(pain_regions or [])
    if body_region and body_region not in explicit_regions:
        explicit_regions.append(body_region)
    if target_action:
        for region in target_action.body_regions or []:
            if region not in explicit_regions:
                explicit_regions.append(region)
    requested_regions = _detect_requested_regions(base_query, explicit_regions)
    coverage = _coverage_info(requested_regions)
    regions = coverage["supported_regions"] or requested_regions
    red_flags = detect_red_flags(base_query)

    if normalized_type == "action" and target_action:
        related_actions = [target_action]
    elif coverage["coverage_status"] == "unsupported_region":
        related_actions = []
    else:
        related_actions = select_actions_for_request(
            symptoms=base_query,
            pain_regions=coverage["supported_regions"] or regions,
            limit=normalized_limit,
        )

    try:
        from .rag import retrieve_contexts

        if coverage["coverage_status"] == "unsupported_region":
            rag_contexts = []
        else:
            rag_contexts = retrieve_contexts(
                query=base_query,
                limit=normalized_limit,
                body_regions=coverage["supported_regions"] or regions or None,
                kind="action",
            )
            rag_contexts = [
                item for item in rag_contexts
                if (item.get("metadata") or {}).get("kind") == "action"
            ]
    except Exception:
        rag_contexts = []

    safety_notes = [
        "若出现剧烈疼痛、麻木无力、大小便异常、发热或症状快速加重，请停止训练并及时就医。",
        "科普文章不能替代医生诊断，具体训练强度需结合个人病情调整。",
    ]
    fallback = _fallback_generated_article(
        article_type=normalized_type,
        query=base_query,
        regions=regions,
        related_actions=related_actions,
        rag_contexts=rag_contexts,
        safety_notes=safety_notes,
        red_flags=red_flags,
        coverage=coverage,
    )

    if coverage["coverage_status"] == "unsupported_region":
        return fallback

    try:
        from .doubao import generate_summary

        prompt = _build_generated_article_prompt(
            article_type=normalized_type,
            query=base_query,
            regions=regions,
            related_actions=related_actions,
            rag_contexts=rag_contexts,
            safety_notes=safety_notes,
            red_flags=red_flags,
            coverage=coverage,
        )
        result = generate_summary(prompt)
        payload = result.get("json") if isinstance(result, dict) else None
        if not isinstance(payload, dict):
            raise RuntimeError("model returned non-json article")
        return _normalize_generated_article_payload(payload, fallback)
    except Exception:
        return fallback
