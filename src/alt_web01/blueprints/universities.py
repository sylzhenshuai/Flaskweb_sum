"""大学管理蓝图。

提供大学与专业组相关页面的路由：手工添加大学、
手工添加专业组、自动添加大学和专业组。
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
import openai
from sclog_lite import logger
from sedb_mysql import SCDBMySQLError
from werkzeug.wrappers import Response

from alt_web01.ai_services import (
    AIConfigurationError,
    AIResponseFormatError,
    build_auto_page_context,
    run_university_auto_workflow,
)
from alt_web01.university_services import (
    UNIVERSITY_NATURES,
    UNIVERSITY_TYPES,
    list_major_groups,
    list_universities,
    save_major_group,
    save_university,
)

bp = Blueprint("universities", __name__, url_prefix="/universities")


def _resolve_selected_university_id(
    requested_id: str,
    university_ids: set[int],
) -> int | None:
    """解析当前选中的高校。

    Args:
        requested_id: 来自查询参数或表单的高校 ID。
        university_ids: 当前已加载高校主键集合。

    Returns:
        int | None: 合法主键时返回对应高校，否则返回 None。
    """
    if not requested_id:
        return None
    if not requested_id.isdigit():
        return None
    selected_id = int(requested_id)
    return selected_id if selected_id in university_ids else None


@bp.get("/add-manual")
def add_manual() -> str:
    """渲染"手工添加大学"页面。

    Returns:
        页面标题为"手工添加大学"的 HTML 页面。
    """
    try:
        universities = list_universities()
    except (SCDBMySQLError, RuntimeError):
        logger.exception("高校清单读取失败")
        flash("数据库暂时不可用，已显示空清单，请稍后刷新重试", "warning")
        universities = []

    return render_template(
        "universities/add_manual.html",
        title="手工添加大学",
        universities=universities,
        university_types=UNIVERSITY_TYPES,
        university_natures=UNIVERSITY_NATURES,
    )


@bp.post("/add-manual")
def save_manual_university() -> Response:
    """保存或覆盖修改一条高校记录。

    Returns:
        Response: 重定向回高校录入页。
    """
    university_id = request.form.get("university_id", "")
    name = request.form.get("name", "")
    code = request.form.get("code", "")
    school_type = request.form.get("type", "")
    nature = request.form.get("nature", "")

    try:
        university, created = save_university(
            university_id,
            name,
            code,
            school_type,
            nature,
        )
    except ValueError as exc:
        logger.warning(
            "高校保存失败: {} | 输入 university_id={!r} name={!r} code={!r} type={!r} nature={!r}",
            exc,
            university_id,
            name,
            code,
            school_type,
            nature,
        )
        flash(str(exc), "danger")
        return redirect(url_for("universities.add_manual"))
    except (SCDBMySQLError, RuntimeError):
        logger.exception(
            "高校保存时数据库访问失败 | 输入 university_id={!r} name={!r} code={!r}",
            university_id,
            name,
            code,
        )
        flash("高校保存失败，请检查 MySQL 连接配置后重试", "danger")
        return redirect(url_for("universities.add_manual"))

    action = "保存" if created else "更新"
    logger.success(
        "高校{}成功: 名称={} 代码={} 办学类型={} 层次={}",
        action,
        university["name"],
        university["code"],
        university["type"],
        university["nature"],
    )
    flash(f"高校「{university['name']}」{action}成功", "success")
    return redirect(url_for("universities.add_manual"))


@bp.get("/add-major-group")
def add_major_group() -> str:
    """渲染"手工添加专业组"页面。

    Returns:
        页面标题为"手工添加专业组"的 HTML 页面。
    """
    try:
        universities = list_universities()
    except (SCDBMySQLError, RuntimeError):
        logger.exception("高校清单读取失败")
        flash("数据库暂时不可用，已显示空清单，请稍后刷新重试", "warning")
        universities = []

    university_ids = {university["id"] for university in universities}
    selected_university_id = _resolve_selected_university_id(
        request.args.get("university_id", ""),
        university_ids,
    )
    if selected_university_id is None and universities:
        selected_university_id = universities[0]["id"]

    selected_university = next(
        (
            university
            for university in universities
            if university["id"] == selected_university_id
        ),
        None,
    )

    try:
        major_groups = (
            list_major_groups(selected_university_id)
            if selected_university_id is not None
            else []
        )
    except ValueError:
        major_groups = []
    except (SCDBMySQLError, RuntimeError):
        logger.exception("专业组清单读取失败")
        flash("数据库暂时不可用，已显示空清单，请稍后刷新重试", "warning")
        major_groups = []

    return render_template(
        "universities/add_major_group.html",
        title="手工添加专业组",
        universities=universities,
        selected_university=selected_university,
        selected_university_id=selected_university_id,
        major_groups=major_groups,
    )


@bp.post("/add-major-group")
def save_manual_major_group() -> Response:
    """保存或覆盖修改一条专业组记录。

    Returns:
        Response: 重定向回专业组录入页。
    """
    major_group_id = request.form.get("major_group_id", "")
    university_id = request.form.get("university_id", "")
    name = request.form.get("name", "")
    code = request.form.get("code", "")

    try:
        major_group, created = save_major_group(
            major_group_id,
            university_id,
            name,
            code,
        )
    except ValueError as exc:
        logger.warning(
            "专业组保存失败: {} | 输入 major_group_id={!r} university_id={!r} name={!r} code={!r}",
            exc,
            major_group_id,
            university_id,
            name,
            code,
        )
        flash(str(exc), "danger")
        return redirect(
            url_for("universities.add_major_group", university_id=university_id)
        )
    except (SCDBMySQLError, RuntimeError):
        logger.exception(
            "专业组保存时数据库访问失败 | 输入 major_group_id={!r} university_id={!r} name={!r} code={!r}",
            major_group_id,
            university_id,
            name,
            code,
        )
        flash("专业组保存失败，请检查 MySQL 连接配置后重试", "danger")
        return redirect(
            url_for("universities.add_major_group", university_id=university_id)
        )

    action = "保存" if created else "更新"
    logger.success(
        "专业组{}成功: 高校={} 专业组={} 代码={}",
        action,
        major_group["university_name"],
        major_group["name"],
        major_group["code"],
    )
    flash(
        f"专业组「{major_group['name']}」{action}成功（所属高校：{major_group['university_name']}）",
        "success",
    )
    return redirect(
        url_for(
            "universities.add_major_group",
            university_id=major_group["university_id"],
        )
    )


@bp.get("/add-auto")
def add_auto() -> str:
    """渲染"自动添加大学和专业组"页面。

    Returns:
        页面标题为"自动添加大学和专业组"的 HTML 页面。
    """
    selected_model = request.args.get("model", "")
    try:
        context = build_auto_page_context(selected_model=selected_model)
    except (SCDBMySQLError, RuntimeError):
        logger.exception("自动添加页面初始化失败")
        flash("数据库暂时不可用，请稍后刷新重试", "warning")
        context = {
            "title": "自动添加大学和专业组",
            "summary": {
                "total_universities": 0,
                "total_major_groups": 0,
            },
            "prompt_text": "",
            "generated_plan": None,
            "workflow_result": None,
            "universities": [],
            "recent_major_groups": [],
            "selected_university": None,
                "ai_model": selected_model or "deepseek-ai/DeepSeek-V4-Flash",
                "model_options": [selected_model or "deepseek-ai/DeepSeek-V4-Flash"],
        }

    return render_template("universities/add_auto.html", **context)


@bp.post("/add-auto")
def save_auto() -> Response | str:
    """调用 AI 自动生成并保存高校与专业组。

    Returns:
        Response | str: 成功时返回渲染后的自动添加页面，失败时返回同页错误提示。
    """
    prompt_text = request.form.get("prompt", "")
    selected_model = request.form.get("model", "")
    try:
        result = run_university_auto_workflow(prompt_text, selected_model)
        context = build_auto_page_context(
            prompt_text=result["prompt"],
            selected_model=result["model"],
            generated_plan=result["generated_plan"],
            workflow_result=result,
        )
        context.update(
            {
                "prompt_text": result["prompt"],
                "generated_plan": result["generated_plan"],
                "workflow_result": result,
                "ai_model": result["model"],
            }
        )
    except ValueError as exc:
        logger.warning("AI 自动添加输入无效: {}", exc)
        flash(str(exc), "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 400
    except AIConfigurationError as exc:
        logger.warning("AI 自动添加配置缺失: {}", exc)
        flash(str(exc), "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 503
    except AIResponseFormatError as exc:
        logger.warning("AI 自动添加结果格式无效: {}", exc)
        flash(f"AI 返回结果无法解析：{exc}", "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 502
    except openai.APIConnectionError:
        logger.exception("AI 服务连接失败")
        flash("AI 服务暂时不可达，请稍后重试", "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 503
    except openai.APIStatusError as exc:
        logger.exception("AI 服务返回错误状态: status_code={}", exc.status_code)
        flash("AI 服务返回错误，请稍后重试", "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 502
    except (SCDBMySQLError, RuntimeError):
        logger.exception("AI 自动添加时数据库访问失败")
        flash("保存失败，请检查 MySQL 连接配置后重试", "danger")
        context = build_auto_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
        )
        return render_template("universities/add_auto.html", **context), 503

    save_summary = result["save_summary"]
    logger.success(
        "AI 自动添加完成: 新增高校={} 更新高校={} 新增专业组={} 更新专业组={}",
        save_summary["universities_created"],
        save_summary["universities_updated"],
        save_summary["major_groups_created"],
        save_summary["major_groups_updated"],
    )
    flash(
        "AI 自动保存完成："
        f"新增高校 {save_summary['universities_created']} 所，"
        f"更新高校 {save_summary['universities_updated']} 所，"
        f"新增专业组 {save_summary['major_groups_created']} 个，"
        f"更新专业组 {save_summary['major_groups_updated']} 个。",
        "success",
    )
    return render_template("universities/add_auto.html", **context)
