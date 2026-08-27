"""自动添加大学和专业组的 AI 服务层。"""

from __future__ import annotations

import json
import os
import re
from functools import cache
from typing import Any, TypedDict

import openai
from openai import OpenAI

from .university_services import (
    StoredMajorGroup,
    StoredUniversity,
    UniversityCatalogSummary,
    find_major_group_by_code,
    find_major_group_by_name,
    find_university_by_code,
    find_university_by_name,
    get_university_catalog_summary,
    list_major_groups,
    list_recent_major_groups,
    list_universities,
    save_major_group,
    save_university,
)

AI_API_KEY_ENV = "API_KEY_GJLD"
AI_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
AI_MODEL = os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
AI_TIMEOUT_SECONDS = 20.0
_UNIVERSITY_NAME_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fff·（）()]{2,40}?"
    r"(?:大学|学院|职业学院|职业技术学院|理工大学|工业大学|师范大学|科技大学|医科大学|中医药大学|农业大学|财经大学|商学院|传媒学院))"
)
_UNIVERSITY_CODE_FROM_TEXT_PATTERN = re.compile(
    r"(?:院校|学校|高校)?代码\s*[:：]?\s*(\d{3})"
)
_MAJOR_GROUP_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fff·（）()]{2,50}?专业组)\s*(\d{1,6})?"
)
_LEADING_UNIVERSITY_VERB_PATTERN = re.compile(
    r"^(?:帮我|帮忙|请把|请给|请|给|把|向|将|对|往)+"
)
_LEADING_MAJOR_GROUP_VERB_PATTERN = re.compile(
    r"^(?:新增|新建|添加|增加|补一下|补充|补一个|补个|加一个|加上|设立|开设|下设|再加|再补)+"
)


class AIGeneratedUniversity(TypedDict):
    """AI 返回的高校记录。"""

    name: str
    code: str
    type: str
    nature: str
    major_groups: list[dict[str, str]]


class AIAutoPlan(TypedDict):
    """AI 生成的完整批量录入计划。"""

    universities: list[AIGeneratedUniversity]


class AIAutoSaveSummary(TypedDict):
    """自动保存执行结果。"""

    universities_created: int
    universities_updated: int
    major_groups_created: int
    major_groups_updated: int
    universities: list[StoredUniversity]
    major_groups: list[StoredMajorGroup]


class AIAutoWorkflowResult(TypedDict):
    """自动生成并保存后的页面返回数据。"""

    model: str
    prompt: str
    summary: UniversityCatalogSummary
    generated_plan: AIAutoPlan
    save_summary: AIAutoSaveSummary
    result_universities: list[AIGeneratedUniversity]


class AIConfigurationError(RuntimeError):
    """AI 配置缺失或不完整时抛出。"""


class AIResponseFormatError(RuntimeError):
    """AI 返回结果不符合预期结构时抛出。"""


def _normalize_model_fallbacks() -> list[str]:
    """兼容旧名字，保留内部调用稳定性。"""
    return _configured_model_fallbacks()


def _configured_model_fallbacks() -> list[str]:
    """返回环境中配置的候选模型列表。

    Returns:
        list[str]: 去重后的候选模型 ID 列表。
    """
    configured = os.getenv("SILICONFLOW_MODEL_OPTIONS", "")
    candidates = [item.strip() for item in configured.split(",") if item.strip()]
    ordered = [AI_MODEL, *candidates]
    return list(dict.fromkeys(ordered))


def _create_ai_client() -> OpenAI:
    """创建 OpenAI-compatible 客户端。

    Returns:
        OpenAI: 配置完成的同步客户端。

    Raises:
        AIConfigurationError: 未找到必需的 API Key 时抛出。
    """
    api_key = os.getenv(AI_API_KEY_ENV)
    if not api_key:
        raise AIConfigurationError(
            f"未找到 {AI_API_KEY_ENV}，请先在运行环境中配置对应密钥。"
        )

    return OpenAI(
        api_key=api_key,
        base_url=AI_BASE_URL,
        timeout=AI_TIMEOUT_SECONDS,
    )


@cache
def _cached_available_models() -> tuple[str, ...]:
    """从上游服务读取当前账号可用模型列表。

    Returns:
        tuple[str, ...]: 模型 ID 元组。

    Raises:
        AIConfigurationError: 无法获得任何模型时抛出。
    """
    client = _create_ai_client()
    response = client.models.list()
    items = getattr(response, "data", response)
    models: list[str] = []
    for item in items:
        model_id = getattr(item, "id", None)
        if model_id is None and isinstance(item, dict):
            model_id = item.get("id")
        if model_id:
            models.append(str(model_id))

    deduplicated = tuple(dict.fromkeys(models))
    if not deduplicated:
        raise AIConfigurationError("AI 服务未返回可用模型列表")
    return deduplicated


def list_available_models() -> list[str]:
    """返回页面可选模型列表。

    Returns:
        list[str]: 优先使用上游实时模型列表；失败时退回到环境配置。
    """
    try:
        return list(_cached_available_models())
    except Exception:
        return _configured_model_fallbacks()


def _resolve_selected_model(model: str | None) -> str:
    """解析页面传入的模型 ID。

    Args:
        model: 用户选择或输入的模型 ID。

    Returns:
        str: 归一化后的模型 ID。
    """
    selected = (model or "").strip()
    return selected or AI_MODEL


def _build_system_prompt(summary: UniversityCatalogSummary) -> str:
    """构造 AI 系统提示词。

    Args:
        summary: 当前高校与专业组统计。

    Returns:
        str: 面向结构化抽取的系统提示词。
    """
    return (
        "你是高校档案录入助手。"
        "用户输入可能是口语、说明句、需求句、补充句，也可能夹杂无关内容。"
        "只要出现大学、学院、学校、院校、专业组、院校代码、专业组代码等相关信息，"
        "都要从自然语言中尽可能抽取出可保存的高校及专业组。"
        "并严格输出 JSON 对象，不要输出 Markdown 或额外说明。"
        "JSON 结构必须为: "
        '{"universities": ['
        '{"name": "高校名称", "code": "三位数字", "type": "民办或公办", '
        '"nature": "985/211/一本/其他", '
        '"major_groups": [{"name": "专业组名称", "code": "1至6位数字"}]}'
        "]}。"
        "如果用户只描述一所高校，也必须放在 universities 数组中。"
        "如果用户是给已有高校补充专业组，而没有重复说明高校代码、办学类型或层次，"
        "可以把未知字段写成空字符串，系统会结合已有数据库补全。"
        "如果层次没有明确提及，填 其他。"
        "把公立、公办统一写成 公办；把私立、民办、独立学院统一写成 民办。"
        "把一本、本科一批、一批统一写成 一本；如果同时出现 985 和 211，填 985。"
        "如果用户没有给出专业组，可返回空数组。"
        "不要输出与高校录入无关的内容。"
        "当前系统已有高校数为 "
        f"{summary['total_universities']}，已有专业组数为 {summary['total_major_groups']}。"
    )


def _load_response_json(text: str) -> dict[str, Any]:
    """尽量从模型返回文本中恢复 JSON 对象。

    Args:
        text: 模型原始输出。

    Returns:
        dict[str, Any]: 解析后的 JSON 对象。

    Raises:
        AIResponseFormatError: 恢复失败时抛出。
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIResponseFormatError("AI 返回内容不是合法 JSON") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIResponseFormatError("AI 返回内容不是合法 JSON") from exc

    if not isinstance(data, dict):
        raise AIResponseFormatError("AI 返回的根节点必须是对象")
    return data


def _extract_university_code_from_text(text: str) -> str:
    """从自然语言中提取三位院校代码。

    Args:
        text: 原始自然语言。

    Returns:
        str: 命中时返回三位数字，否则返回空字符串。
    """
    match = _UNIVERSITY_CODE_FROM_TEXT_PATTERN.search(text)
    return match.group(1) if match else ""


def _extract_university_type_from_text(text: str) -> str:
    """从自然语言中提取高校类型。

    Args:
        text: 原始自然语言。

    Returns:
        str: 命中时返回公办或民办，否则返回空字符串。
    """
    if any(keyword in text for keyword in ("民办", "私立", "独立学院", "私办")):
        return "民办"
    if any(keyword in text for keyword in ("公办", "公立")):
        return "公办"
    return ""


def _extract_university_nature_from_text(text: str) -> str:
    """从自然语言中提取高校层次。

    Args:
        text: 原始自然语言。

    Returns:
        str: 命中时返回 985、211、一本 或 其他。
    """
    if "985" in text:
        return "985"
    if "211" in text:
        return "211"
    if any(keyword in text for keyword in ("一本", "本科一批", "一批")):
        return "一本"
    return "其他" if "其他" in text else ""


def _extract_major_groups_from_text(text: str) -> list[dict[str, str]]:
    """从自然语言中提取专业组列表。

    Args:
        text: 原始自然语言。

    Returns:
        list[dict[str, str]]: 抽取出的专业组名称和代码列表。
    """
    groups: list[dict[str, str]] = []
    for name, code in _MAJOR_GROUP_PATTERN.findall(text):
        groups.append(
            {
                "name": _clean_major_group_name(name),
                "code": _digits_only(code or "", 6),
            }
        )
    return groups


def _clean_university_name(value: str) -> str:
    """清理高校名前导动作词。

    Args:
        value: 原始高校名称片段。

    Returns:
        str: 清理后的高校名称。
    """
    clean = value.strip()
    previous = None
    while previous != clean:
        previous = clean
        clean = _LEADING_UNIVERSITY_VERB_PATTERN.sub("", clean).strip()
    return clean


def _clean_major_group_name(value: str) -> str:
    """清理专业组名前导动作词和高校名称。

    Args:
        value: 原始专业组名称片段。

    Returns:
        str: 清理后的专业组名称。
    """
    clean = value.strip()
    previous = None
    while previous != clean:
        previous = clean
        clean = _clean_university_name(clean)
        university_match = _UNIVERSITY_NAME_PATTERN.match(clean)
        if university_match:
            clean = clean[university_match.end() :].strip(" 的，,:：")
        clean = _LEADING_MAJOR_GROUP_VERB_PATTERN.sub("", clean).strip()
    return clean


def _extract_plan_from_prompt(prompt: str) -> AIAutoPlan:
    """从自然语言中做一层本地兜底抽取。

    Args:
        prompt: 用户输入的自然语言。

    Returns:
        AIAutoPlan: 基于正则规则提取出的高校计划。
    """
    normalized = re.sub(r"(另外|再新增|再加|顺便|同时|还有|以及)", "；", prompt)
    segments = [
        segment.strip(" ，,；;。\n\t")
        for segment in re.split(r"[；;。！？!?]", normalized)
        if segment.strip(" ，,；;。\n\t")
    ]

    universities: list[AIGeneratedUniversity] = []
    current_university: AIGeneratedUniversity | None = None
    for segment in segments:
        names = [
            _clean_university_name(match.group(1))
            for match in _UNIVERSITY_NAME_PATTERN.finditer(segment)
        ]
        if names:
            for name in names:
                current_university = AIGeneratedUniversity(
                    name=name,
                    code=_extract_university_code_from_text(segment),
                    type=_extract_university_type_from_text(segment),
                    nature=_extract_university_nature_from_text(segment),
                    major_groups=_extract_major_groups_from_text(segment),
                )
                universities.append(current_university)
            continue

        if current_university is not None:
            current_university["major_groups"].extend(_extract_major_groups_from_text(segment))
            if not current_university["code"]:
                current_university["code"] = _extract_university_code_from_text(segment)
            if not current_university["type"]:
                current_university["type"] = _extract_university_type_from_text(segment)
            if not current_university["nature"]:
                current_university["nature"] = _extract_university_nature_from_text(segment)

    return AIAutoPlan(universities=universities)


def _merge_major_group_lists(
    primary: list[dict[str, str]],
    fallback: list[dict[str, str]],
) -> list[dict[str, str]]:
    """把 AI 专业组列表与本地兜底列表合并。

    Args:
        primary: AI 输出的专业组列表。
        fallback: 本地规则提取出的专业组列表。

    Returns:
        list[dict[str, str]]: 合并后的专业组列表。
    """
    merged: list[dict[str, str]] = []
    used_fallback_indexes: set[int] = set()
    for index, item in enumerate(primary):
        best_match_index: int | None = None
        for fallback_index, candidate in enumerate(fallback):
            if item["code"] and candidate["code"] and item["code"] == candidate["code"]:
                best_match_index = fallback_index
                break
            if item["name"] and candidate["name"] and item["name"] == candidate["name"]:
                best_match_index = fallback_index
                break
        if best_match_index is None and len(primary) == 1 and len(fallback) == 1:
            best_match_index = 0

        if best_match_index is not None:
            candidate = fallback[best_match_index]
            used_fallback_indexes.add(best_match_index)
            merged.append(
                {
                    "name": item["name"] or candidate["name"],
                    "code": item["code"] or candidate["code"],
                }
            )
            continue

        merged.append(item)

    for fallback_index, candidate in enumerate(fallback):
        if fallback_index not in used_fallback_indexes:
            merged.append(candidate)
    return merged


def _merge_university_payloads(
    primary: AIGeneratedUniversity,
    fallback: AIGeneratedUniversity,
) -> AIGeneratedUniversity:
    """把 AI 高校条目与本地兜底条目合并。

    Args:
        primary: AI 输出的高校条目。
        fallback: 本地规则提取出的高校条目。

    Returns:
        AIGeneratedUniversity: 合并后的高校条目。
    """
    return AIGeneratedUniversity(
        name=primary["name"] or fallback["name"],
        code=primary["code"] or fallback["code"],
        type=primary["type"] or fallback["type"],
        nature=primary["nature"] or fallback["nature"],
        major_groups=_merge_major_group_lists(
            primary["major_groups"],
            fallback["major_groups"],
        ),
    )


def _supplement_university_plan(prompt: str, plan: AIAutoPlan) -> AIAutoPlan:
    """用本地规则抽取结果补齐 AI 计划。

    Args:
        prompt: 用户原始自然语言。
        plan: AI 输出的计划。

    Returns:
        AIAutoPlan: 补齐后的计划。
    """
    fallback_plan = _extract_plan_from_prompt(prompt)
    fallback_items = fallback_plan["universities"]
    if not fallback_items:
        return plan

    primary_items = [_coerce_university_payload(item) for item in plan["universities"]]
    if not primary_items:
        return fallback_plan

    merged: list[AIGeneratedUniversity] = []
    used_fallback_indexes: set[int] = set()
    for index, item in enumerate(primary_items):
        match_index: int | None = None
        for fallback_index, fallback_item in enumerate(fallback_items):
            if item["code"] and fallback_item["code"] and item["code"] == fallback_item["code"]:
                match_index = fallback_index
                break
            if item["name"] and fallback_item["name"] and item["name"] == fallback_item["name"]:
                match_index = fallback_index
                break
        if match_index is None and index < len(fallback_items):
            if not item["name"] or not item["code"] or not item["major_groups"]:
                match_index = index

        if match_index is not None:
            used_fallback_indexes.add(match_index)
            merged.append(_merge_university_payloads(item, fallback_items[match_index]))
            continue

        merged.append(item)

    for fallback_index, fallback_item in enumerate(fallback_items):
        if fallback_index not in used_fallback_indexes:
            merged.append(fallback_item)

    return AIAutoPlan(universities=merged)


def _extract_response_json(content: str) -> AIAutoPlan:
    """从模型输出中提取 JSON。

    Args:
        content: 模型原始文本输出。

    Returns:
        AIAutoPlan: 结构化计划。

    Raises:
        AIResponseFormatError: 输出为空或 JSON 不合法时抛出。
    """
    raw = content.strip()
    if not raw:
        raise AIResponseFormatError("AI 未返回任何内容")

    if raw.startswith("```"):
        first_newline = raw.find("\n")
        last_fence = raw.rfind("```")
        if first_newline != -1 and last_fence != -1 and last_fence > first_newline:
            raw = raw[first_newline + 1:last_fence].strip()

    data = _load_response_json(raw)
    universities = data.get("universities")
    if universities is None:
        for key in ("schools", "colleges", "items", "data"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                universities = candidate
                break
    if not isinstance(universities, list):
        raise AIResponseFormatError("AI 返回中缺少 universities 数组")

    return AIAutoPlan(universities=universities)


def _request_ai_plan(
    client: OpenAI,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    """向 AI 发起结构化提取请求。

    Args:
        client: OpenAI-compatible 客户端。
        model: 本次调用使用的模型 ID。
        messages: Chat Completions 消息数组。

    Returns:
        str: 模型输出文本。
    """
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except openai.APIStatusError as exc:
        if exc.status_code not in {400, 422}:
            raise
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    return completion.choices[0].message.content or ""


def generate_university_plan(prompt: str, model: str | None = None) -> AIAutoPlan:
    """使用 AI 把自然语言转成高校与专业组计划。

    Args:
        prompt: 用户输入的自然语言说明。
        model: 用户选定的模型 ID。

    Returns:
        AIAutoPlan: AI 解析出的结构化保存计划。

    Raises:
        ValueError: 输入为空时抛出。
        AIConfigurationError: 密钥缺失时抛出。
        AIResponseFormatError: AI 返回结构不合法时抛出。
        openai.APIError: 模型调用失败时抛出。
    """
    if not prompt or not prompt.strip():
        raise ValueError("请输入要自动添加的高校和专业组描述")

    client = _create_ai_client()
    summary = get_university_catalog_summary()
    selected_model = _resolve_selected_model(model)
    messages = [
        {
            "role": "system",
            "content": _build_system_prompt(summary),
        },
        {
            "role": "user",
            "content": prompt.strip(),
        },
    ]
    content = _request_ai_plan(client, selected_model, messages)
    try:
        plan = _extract_response_json(content)
    except AIResponseFormatError:
        fallback_plan = _extract_plan_from_prompt(prompt)
        if fallback_plan["universities"]:
            return fallback_plan
        raise
    return _supplement_university_plan(prompt, plan)


def _normalize_university_type(
    value: str,
    existing_university: StoredUniversity | None,
) -> str:
    """归一化高校办学类型。

    Args:
        value: AI 返回的办学类型。
        existing_university: 已命中的高校记录。

    Returns:
        str: 归一化后的办学类型。
    """
    clean = value.strip()
    if not clean:
        return existing_university["type"] if existing_university else ""
    if clean in {"公办", "公立", "公办院校"}:
        return "公办"
    if clean in {"民办", "私立", "私办", "独立学院"}:
        return "民办"
    return clean


def _normalize_university_nature(
    value: str,
    existing_university: StoredUniversity | None,
) -> str:
    """归一化高校层次。

    Args:
        value: AI 返回的高校层次。
        existing_university: 已命中的高校记录。

    Returns:
        str: 归一化后的高校层次。
    """
    clean = value.strip()
    if not clean:
        return existing_university["nature"] if existing_university else "其他"
    if "985" in clean:
        return "985"
    if "211" in clean:
        return "211"
    if any(keyword in clean for keyword in ("一本", "本科一批", "一批")):
        return "一本"
    if clean == "其他":
        return existing_university["nature"] if existing_university else "其他"
    return existing_university["nature"] if existing_university else "其他"


def _digits_only(value: str, max_length: int) -> str:
    """提取字符串中的数字并截断到指定长度。

    Args:
        value: 原始字符串。
        max_length: 允许的最大长度。

    Returns:
        str: 仅保留数字后的结果。
    """
    return "".join(character for character in value if character.isdigit())[:max_length]


def _complete_generated_university(
    payload: AIGeneratedUniversity,
    existing_university: StoredUniversity | None,
) -> AIGeneratedUniversity:
    """结合现有数据库补全 AI 提取出的高校字段。

    Args:
        payload: AI 提取出的高校条目。
        existing_university: 已匹配到的高校记录。

    Returns:
        AIGeneratedUniversity: 可用于保存的完整高校对象。

    Raises:
        AIResponseFormatError: 补全后仍缺失关键字段时抛出。
    """
    name = payload["name"] or (existing_university["name"] if existing_university else "")
    code = _digits_only(payload["code"], 3) or (
        existing_university["code"] if existing_university else ""
    )
    school_type = _normalize_university_type(payload["type"], existing_university)
    nature = _normalize_university_nature(payload["nature"], existing_university)

    if not name:
        raise AIResponseFormatError("AI 未提取出高校名称")
    if not code:
        raise AIResponseFormatError("AI 未提取出高校代码")
    if not school_type:
        raise AIResponseFormatError("AI 未提取出高校类型")

    return AIGeneratedUniversity(
        name=name,
        code=code,
        type=school_type,
        nature=nature,
        major_groups=payload["major_groups"],
    )


def _coerce_major_group_item(item: dict[str, str]) -> dict[str, str]:
    """归一化单个专业组字段。

    Args:
        item: AI 返回的单个专业组条目。

    Returns:
        dict[str, str]: 归一化后的专业组条目。
    """
    return {
        "name": str(item.get("name", "")).strip(),
        "code": _digits_only(str(item.get("code", "")).strip(), 6),
    }


def _normalize_major_groups(value: Any) -> list[dict[str, str]]:
    """把 AI 输出的专业组数组归一化为字典列表。

    Args:
        value: AI 返回的 major_groups 字段。

    Returns:
        list[dict[str, str]]: 归一化后的专业组列表。

    Raises:
        AIResponseFormatError: 字段结构错误时抛出。
    """
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise AIResponseFormatError("major_groups 必须是数组")

    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AIResponseFormatError("专业组条目必须是对象")
        normalized.append(_coerce_major_group_item(item))
    return normalized


def _coerce_university_payload(item: Any) -> AIGeneratedUniversity:
    """把 AI 输出的高校对象收敛成可保存结构。

    Args:
        item: AI 返回的单个高校对象。

    Returns:
        AIGeneratedUniversity: 归一化后的高校对象。

    Raises:
        AIResponseFormatError: 字段结构错误时抛出。
    """
    if not isinstance(item, dict):
        raise AIResponseFormatError("高校条目必须是对象")

    major_groups_value = item.get("major_groups")
    if major_groups_value is None:
        for key in ("groups", "majors", "majorGroups"):
            if key in item:
                major_groups_value = item[key]
                break

    return AIGeneratedUniversity(
        name=str(item.get("name", "")).strip(),
        code=str(item.get("code", item.get("school_code", ""))).strip(),
        type=str(item.get("type", item.get("school_type", ""))).strip(),
        nature=str(item.get("nature", item.get("school_nature", ""))).strip(),
        major_groups=_normalize_major_groups(major_groups_value or []),
    )


def apply_university_plan(plan: AIAutoPlan) -> AIAutoSaveSummary:
    """把 AI 计划保存到数据库。

    Args:
        plan: AI 生成的结构化计划。

    Returns:
        AIAutoSaveSummary: 新增与更新结果统计。

    Raises:
        AIResponseFormatError: 计划为空或字段结构错误时抛出。
        ValueError: 经过既有业务校验后不合法时抛出。
    """
    items = plan.get("universities", [])
    if not items:
        raise AIResponseFormatError("AI 未生成任何高校记录")

    saved_universities: list[StoredUniversity] = []
    saved_major_groups: list[StoredMajorGroup] = []
    universities_created = 0
    universities_updated = 0
    major_groups_created = 0
    major_groups_updated = 0

    for raw_item in items:
        payload = _coerce_university_payload(raw_item)
        existing_university = find_university_by_code(payload["code"])
        if existing_university is None:
            existing_university = find_university_by_name(payload["name"])
        payload = _complete_generated_university(payload, existing_university)

        university, created = save_university(
            str(existing_university["id"]) if existing_university else "",
            payload["name"],
            payload["code"],
            payload["type"],
            payload["nature"],
        )
        saved_universities.append(university)
        if created:
            universities_created += 1
        else:
            universities_updated += 1

        for major_group_payload in payload["major_groups"]:
            existing_major_group = find_major_group_by_code(
                university["id"],
                major_group_payload["code"],
            )
            if existing_major_group is None:
                existing_major_group = find_major_group_by_name(
                    university["id"],
                    major_group_payload["name"],
                )
            major_group_payload = _coerce_major_group_item(major_group_payload)
            if not major_group_payload["name"] and existing_major_group is not None:
                major_group_payload["name"] = existing_major_group["name"]
            if not major_group_payload["code"] and existing_major_group is not None:
                major_group_payload["code"] = existing_major_group["code"]
            if not major_group_payload["name"]:
                raise AIResponseFormatError("AI 未提取出专业组名称")
            if not major_group_payload["code"]:
                raise AIResponseFormatError("AI 未提取出专业组代码")

            major_group, major_group_created = save_major_group(
                str(existing_major_group["id"]) if existing_major_group else "",
                str(university["id"]),
                major_group_payload["name"],
                major_group_payload["code"],
            )
            saved_major_groups.append(major_group)
            if major_group_created:
                major_groups_created += 1
            else:
                major_groups_updated += 1

    return AIAutoSaveSummary(
        universities_created=universities_created,
        universities_updated=universities_updated,
        major_groups_created=major_groups_created,
        major_groups_updated=major_groups_updated,
        universities=saved_universities,
        major_groups=saved_major_groups,
    )


def _build_result_universities(save_summary: AIAutoSaveSummary) -> list[AIGeneratedUniversity]:
    """把实际保存结果整理成页面展示结构。

    Args:
        save_summary: 自动保存执行结果。

    Returns:
        list[AIGeneratedUniversity]: 按保存顺序整理后的高校结果列表。
    """
    grouped_major_groups: dict[int, list[dict[str, str]]] = {}
    for major_group in save_summary["major_groups"]:
        grouped_major_groups.setdefault(major_group["university_id"], []).append(
            {
                "name": major_group["name"],
                "code": major_group["code"],
            }
        )

    return [
        AIGeneratedUniversity(
            name=university["name"],
            code=university["code"],
            type=university["type"],
            nature=university["nature"],
            major_groups=grouped_major_groups.get(university["id"], []),
        )
        for university in save_summary["universities"]
    ]


def run_university_auto_workflow(
    prompt: str,
    model: str | None = None,
) -> AIAutoWorkflowResult:
    """执行完整的 AI 自动添加流程。

    Args:
        prompt: 用户输入的自然语言需求。
        model: 用户选定的模型 ID。

    Returns:
        AIAutoWorkflowResult: 页面所需的完整 AI 结果数据。
    """
    selected_model = _resolve_selected_model(model)
    plan = generate_university_plan(prompt, selected_model)
    save_summary = apply_university_plan(plan)
    return AIAutoWorkflowResult(
        model=selected_model,
        prompt=prompt.strip(),
        summary=get_university_catalog_summary(),
        generated_plan=plan,
        save_summary=save_summary,
        result_universities=_build_result_universities(save_summary),
    )


def build_auto_page_context(
    *,
    prompt_text: str = "",
    selected_model: str | None = None,
    generated_plan: AIAutoPlan | None = None,
    workflow_result: AIAutoWorkflowResult | None = None,
) -> dict[str, Any]:
    """构造自动添加页面的基础上下文。

    Args:
        prompt_text: 页面中回显的自然语言输入。
        selected_model: 页面当前选定的模型。
        generated_plan: 最近一次 AI 解析出的结构化计划。
        workflow_result: 最近一次自动保存结果。

    Returns:
        dict[str, Any]: 自动添加页面默认上下文。
    """
    summary = get_university_catalog_summary()
    universities = list_universities()
    current_model = _resolve_selected_model(selected_model)
    model_options = list_available_models()
    if current_model not in model_options:
        model_options = [current_model, *model_options]
    recent_major_groups = list_recent_major_groups()
    return {
        "title": "自动添加大学和专业组",
        "summary": summary,
        "prompt_text": prompt_text,
        "generated_plan": generated_plan,
        "workflow_result": workflow_result,
        "universities": universities,
        "recent_major_groups": recent_major_groups,
        "selected_university": universities[-1] if universities else None,
        "ai_model": current_model,
        "model_options": model_options,
    }