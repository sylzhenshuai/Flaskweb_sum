"""自动入学的 AI 解析与保存服务。"""

from __future__ import annotations

import datetime
import json
import re
from typing import Any, TypedDict

from .ai_services import (
    AIConfigurationError,
    AIResponseFormatError,
    _create_ai_client,
    _load_response_json,
    _request_ai_plan,
    _resolve_selected_model,
    list_available_models,
)
from .enrollment_services import StoredEnrollment, create_enrollment, list_enrollments
from .services import StoredStudent, list_students
from .university_services import (
    StoredMajorGroup,
    StoredUniversity,
    list_recent_major_groups,
    list_universities,
)


class AutoEnrollmentPlan(TypedDict):
    """AI 生成的入学安排计划。"""

    enrollments: list[dict[str, Any]]


class AutoEnrollmentSaveSummary(TypedDict):
    """自动入学保存结果。"""

    created: int
    enrollments: list[StoredEnrollment]


class AutoEnrollmentWorkflowResult(TypedDict):
    """自动入学页面需要展示的完整结果。"""

    model: str
    prompt: str
    plan: AutoEnrollmentPlan
    save_summary: AutoEnrollmentSaveSummary
    enrollments: list[StoredEnrollment]


def _catalog_payload(
    students: list[StoredStudent],
    universities: list[StoredUniversity],
    major_groups: list[StoredMajorGroup],
) -> dict[str, list[dict[str, Any]]]:
    """把候选记录转换为发送给模型的轻量字段。"""
    return {
        "students": [{"id": item["id"], "name": item["name"]} for item in students],
        "universities": [
            {"id": item["id"], "name": item["name"], "code": item["code"]}
            for item in universities
        ],
        "major_groups": [
            {
                "id": item["id"],
                "university_id": item["university_id"],
                "name": item["name"],
                "code": item["code"],
            }
            for item in major_groups
        ],
    }


def _build_system_prompt(
    students: list[StoredStudent],
    universities: list[StoredUniversity],
    major_groups: list[StoredMajorGroup],
) -> str:
    """构造结构化入学安排提示词。"""
    catalog = json.dumps(
        _catalog_payload(students, universities, major_groups),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "你是入学安排助手。根据用户描述，从候选记录中提取一个或多个入学安排。"
        "只返回 JSON，不要解释。格式必须为 "
        '{"enrollments":[{"student_id":1,"university_id":2,'
        '"major_group_id":3,"enrolled_on":"2026-08-27"}]}。'
        "student_id、university_id、major_group_id 必须来自候选记录；"
        "未写入学日期时使用今天。不要创建候选记录之外的对象。"
        f"候选记录如下：{catalog}"
    )


def _load_plan_json(content: str) -> AutoEnrollmentPlan:
    """从模型文本中读取入学计划。"""
    raw = content.strip()
    if not raw:
        raise AIResponseFormatError("AI 未返回任何内容")
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        last_fence = raw.rfind("```")
        if first_newline != -1 and last_fence > first_newline:
            raw = raw[first_newline + 1 : last_fence].strip()

    try:
        data = _load_response_json(raw)
    except AIResponseFormatError:
        raise
    except (TypeError, ValueError) as exc:
        raise AIResponseFormatError("AI 返回内容不是合法 JSON") from exc
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("enrollments")
        if items is None:
            for key in ("assignments", "items", "data"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
    else:
        items = None
    if not isinstance(items, list):
        raise AIResponseFormatError("AI 返回中缺少 enrollments 数组")
    return AutoEnrollmentPlan(enrollments=[item for item in items if isinstance(item, dict)])


def _field(item: dict[str, Any], *keys: str) -> Any:
    """按别名读取模型字段，兼容嵌套对象。"""
    for key in keys:
        if key in item:
            value = item[key]
            if isinstance(value, dict):
                return value.get("id") or value.get("name") or value.get("code") or ""
            return value
    return ""


def _coerce_assignment(item: dict[str, Any]) -> dict[str, Any]:
    """统一模型输出中的单条安排字段。"""
    return {
        "student_id": str(
            _field(item, "student_id", "studentId", "student", "学生ID", "学生")
        ).strip(),
        "student_name": str(
            _field(item, "student_name", "studentName", "姓名", "学生姓名")
        ).strip(),
        "university_id": str(
            _field(
                item,
                "university_id",
                "universityId",
                "school_id",
                "schoolId",
                "university",
                "school",
                "高校ID",
                "学校ID",
                "高校",
                "学校",
            )
        ).strip(),
        "university_name": str(
            _field(
                item,
                "university_name",
                "universityName",
                "school_name",
                "高校名称",
                "学校名称",
            )
        ).strip(),
        "university_code": str(
            _field(
                item,
                "university_code",
                "universityCode",
                "school_code",
                "高校代码",
                "学校代码",
            )
        ).strip(),
        "major_group_id": str(
            _field(
                item,
                "major_group_id",
                "majorGroupId",
                "majorGroup",
                "major_group",
                "major",
                "专业组ID",
                "专业组",
            )
        ).strip(),
        "major_group_name": str(
            _field(
                item,
                "major_group_name",
                "majorGroupName",
                "major_name",
                "专业组名称",
            )
        ).strip(),
        "major_group_code": str(
            _field(
                item,
                "major_group_code",
                "majorGroupCode",
                "major_code",
                "专业组代码",
            )
        ).strip(),
        "enrolled_on": str(
            _field(item, "enrolled_on", "enrolledOn", "date", "入学日期")
        ).strip()
        or datetime.date.today().isoformat(),
    }


def _local_plan(
    prompt: str,
    students: list[StoredStudent],
    universities: list[StoredUniversity],
    major_groups: list[StoredMajorGroup],
) -> AutoEnrollmentPlan:
    """在模型输出不可解析时，按候选名称做一层本地兜底。"""
    segments = [part.strip() for part in prompt.replace("另外", "；").split("；") if part.strip()]
    items: list[dict[str, Any]] = []
    for segment in segments:
        matched_students = [item for item in students if item["name"] in segment]
        matched_universities = [item for item in universities if item["name"] in segment]
        matched_groups = [item for item in major_groups if item["name"] in segment]
        for student in matched_students:
            for university in matched_universities:
                groups = [
                    item for item in matched_groups if item["university_id"] == university["id"]
                ]
                for group in groups:
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", segment)
                    items.append(
                        {
                            "student_id": student["id"],
                            "university_id": university["id"],
                            "major_group_id": group["id"],
                            "enrolled_on": date_match.group(0)
                            if date_match
                            else datetime.date.today().isoformat(),
                        }
                    )
    return AutoEnrollmentPlan(enrollments=items)


def generate_enrollment_plan(prompt: str, model: str | None = None) -> AutoEnrollmentPlan:
    """使用 AI 将自然语言转换为入学安排计划。"""
    if not prompt or not prompt.strip():
        raise ValueError("请输入学生、学校和专业组的安排描述")

    students = list_students()
    universities = list_universities()
    major_groups = list_recent_major_groups()
    client = _create_ai_client()
    selected_model = _resolve_selected_model(model)
    content = _request_ai_plan(
        client,
        selected_model,
        [
            {"role": "system", "content": _build_system_prompt(students, universities, major_groups)},
            {"role": "user", "content": prompt.strip()},
        ],
    )
    try:
        plan = _load_plan_json(content)
    except AIResponseFormatError:
        fallback = _local_plan(prompt, students, universities, major_groups)
        if fallback["enrollments"]:
            return fallback
        raise
    if not plan["enrollments"]:
        fallback = _local_plan(prompt, students, universities, major_groups)
        if fallback["enrollments"]:
            return fallback
    return AutoEnrollmentPlan(
        enrollments=[_coerce_assignment(item) for item in plan["enrollments"]]
    )


def _resolve_id(
    value: str,
    candidates: list[dict[str, Any]],
    label: str,
    *,
    name: str = "",
    code: str = "",
) -> int:
    """按主键、名称或代码解析候选记录。"""
    if value.isdigit() and any(int(item["id"]) == int(value) for item in candidates):
        return int(value)
    matches = [item for item in candidates if name and item.get("name") == name]
    if not matches and value:
        matches = [item for item in candidates if item.get("name") == value]
    if not matches and code:
        matches = [item for item in candidates if item.get("code") == code]
    if len(matches) == 1:
        return int(matches[0]["id"])
    if len(matches) > 1:
        raise ValueError(f"{label}名称对应多条记录，请在描述中提供 ID")
    raise ValueError(f"未找到有效的{label}，请检查描述或先完成手动录入")


def apply_enrollment_plan(plan: AutoEnrollmentPlan) -> AutoEnrollmentSaveSummary:
    """校验并保存 AI 生成的入学安排。"""
    if not plan.get("enrollments"):
        raise AIResponseFormatError("AI 未生成任何入学安排")

    students = [dict(item) for item in list_students()]
    universities = [dict(item) for item in list_universities()]
    major_groups = [dict(item) for item in list_recent_major_groups()]
    existing_student_ids = {item["student_id"] for item in list_enrollments()}
    resolved: list[tuple[str, str, str, str]] = []
    seen_students: set[int] = set()
    for raw_item in plan["enrollments"]:
        item = _coerce_assignment(raw_item)
        student_id = _resolve_id(item["student_id"], students, "学生", name=item["student_name"])
        university_id = _resolve_id(
            item["university_id"], universities, "高校", name=item["university_name"], code=item["university_code"]
        )
        major_candidates = [item for item in major_groups if int(item["university_id"]) == university_id]
        major_id = _resolve_id(
            item["major_group_id"],
            major_candidates,
            "专业组",
            name=item["major_group_name"],
            code=item["major_group_code"],
        )
        if student_id in seen_students:
            raise ValueError("同一份安排中不能重复安排同一名学生")
        if student_id in existing_student_ids:
            raise ValueError("该学生已经安排入学")
        seen_students.add(student_id)
        try:
            enrolled_on = datetime.date.fromisoformat(item["enrolled_on"]).isoformat()
        except ValueError:
            raise ValueError("入学日期格式不正确，应为 YYYY-MM-DD") from None
        resolved.append((str(student_id), str(university_id), str(major_id), enrolled_on))

    saved = [create_enrollment(*item) for item in resolved]
    return AutoEnrollmentSaveSummary(created=len(saved), enrollments=saved)


def run_enrollment_auto_workflow(
    prompt: str,
    model: str | None = None,
) -> AutoEnrollmentWorkflowResult:
    """执行自动入学的解析、校验和保存流程。"""
    selected_model = _resolve_selected_model(model)
    plan = generate_enrollment_plan(prompt, selected_model)
    save_summary = apply_enrollment_plan(plan)
    return AutoEnrollmentWorkflowResult(
        model=selected_model,
        prompt=prompt.strip(),
        plan=plan,
        save_summary=save_summary,
        enrollments=save_summary["enrollments"],
    )


def build_auto_enrollment_page_context(
    *,
    prompt_text: str = "",
    selected_model: str | None = None,
    workflow_result: AutoEnrollmentWorkflowResult | None = None,
) -> dict[str, Any]:
    """构造自动入学页面上下文。"""
    students = list_students()
    universities = list_universities()
    major_groups = list_recent_major_groups()
    enrollments = list_enrollments()
    current_model = _resolve_selected_model(selected_model)
    model_options = list_available_models()
    if current_model not in model_options:
        model_options = [current_model, *model_options]
    return {
        "title": "自动入学",
        "prompt_text": prompt_text,
        "workflow_result": workflow_result,
        "students": students,
        "universities": universities,
        "major_groups": major_groups,
        "enrollments": enrollments,
        "ai_model": current_model,
        "model_options": model_options,
    }
