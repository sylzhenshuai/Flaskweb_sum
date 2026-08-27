"""入学管理蓝图。

提供入学流程相关页面的路由：手动入学、自动入学。
"""

import datetime

import openai
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sclog_lite import logger
from sedb_mysql import SCDBMySQLError
from werkzeug.wrappers import Response

from alt_web01.ai_services import AIConfigurationError, AIResponseFormatError
from alt_web01.enrollment_services import create_enrollment, list_enrollments
from alt_web01.enrollment_ai_services import (
    build_auto_enrollment_page_context,
    run_enrollment_auto_workflow,
)
from alt_web01.services import list_students
from alt_web01.university_services import (
    list_recent_major_groups,
    list_universities,
)

bp = Blueprint("enrollment", __name__, url_prefix="/enrollment")


@bp.get("/manual")
def manual() -> str:
    """渲染"手动入学"页面。

    Returns:
        页面标题为"手动入学"的 HTML 页面。
    """
    context = {
        "title": "手动入学",
        "students": [],
        "universities": [],
        "major_groups": [],
        "enrollments": [],
        "today": datetime.date.today().isoformat(),
    }
    try:
        context.update(
            students=list_students(),
            universities=list_universities(),
            major_groups=list_recent_major_groups(),
            enrollments=list_enrollments(),
        )
    except (SCDBMySQLError, RuntimeError):
        logger.exception("手动入学页面初始化失败")
        flash("数据库暂时不可用，选项和清单将在恢复后重新加载", "warning")

    return render_template("enrollment/manual.html", **context)


@bp.post("/manual")
def save_manual() -> Response:
    """保存一条手动入学安排并返回页面。"""
    values = (
        request.form.get("student_id", ""),
        request.form.get("university_id", ""),
        request.form.get("major_group_id", ""),
        request.form.get("enrolled_on", ""),
    )
    try:
        enrollment = create_enrollment(*values)
    except ValueError as exc:
        logger.warning("手动入学校验失败: {}", exc)
        flash(str(exc), "danger")
        return redirect(url_for("enrollment.manual"))
    except (SCDBMySQLError, RuntimeError):
        logger.exception("手动入学保存时数据库访问失败")
        flash("入学安排保存失败，请检查 MySQL 连接配置后重试", "danger")
        return redirect(url_for("enrollment.manual"))

    logger.success(
        "手动入学安排成功: 学生={} 高校={} 专业组={} 日期={}",
        enrollment["student_name"],
        enrollment["university_name"],
        enrollment["major_group_name"],
        enrollment["enrolled_on"],
    )
    flash(
        f"已为「{enrollment['student_name']}」安排进入「{enrollment['university_name']}」",
        "success",
    )
    return redirect(url_for("enrollment.manual"))


def _auto_page_context(
    *,
    prompt_text: str = "",
    selected_model: str = "",
    workflow_result=None,
) -> dict:
    """加载自动入学页面数据，数据库不可用时保持页面可访问。"""
    try:
        return build_auto_enrollment_page_context(
            prompt_text=prompt_text,
            selected_model=selected_model,
            workflow_result=workflow_result,
        )
    except (SCDBMySQLError, RuntimeError):
        logger.exception("自动入学页面初始化失败")
        flash("数据库暂时不可用，候选项和清单将在恢复后重新加载", "warning")
        return {
            "title": "自动入学",
            "prompt_text": prompt_text,
            "workflow_result": workflow_result,
            "students": [],
            "universities": [],
            "major_groups": [],
            "enrollments": [],
            "ai_model": selected_model or "deepseek-ai/DeepSeek-V4-Flash",
            "model_options": [selected_model or "deepseek-ai/DeepSeek-V4-Flash"],
        }


def _render_auto_error(prompt_text: str, selected_model: str, status: int):
    """回显自动入学表单并返回指定 HTTP 状态。"""
    return (
        render_template(
            "enrollment/auto.html",
            **_auto_page_context(
                prompt_text=prompt_text,
                selected_model=selected_model,
            ),
        ),
        status,
    )


@bp.get("/auto")
def auto() -> str:
    """渲染"自动入学"页面。

    Returns:
        页面标题为"自动入学"的 HTML 页面。
    """
    context = _auto_page_context(
        prompt_text=request.args.get("prompt", ""),
        selected_model=request.args.get("model", ""),
    )
    return render_template("enrollment/auto.html", **context)


@bp.post("/auto")
def save_auto() -> Response | str:
    """解析自然语言并保存自动入学安排。"""
    prompt_text = request.form.get("prompt", "")
    selected_model = request.form.get("model", "")
    try:
        result = run_enrollment_auto_workflow(prompt_text, selected_model)
    except ValueError as exc:
        logger.warning("自动入学校验失败: {}", exc)
        flash(str(exc), "danger")
        return _render_auto_error(prompt_text, selected_model, 400)
    except AIConfigurationError as exc:
        logger.warning("自动入学配置缺失: {}", exc)
        flash(str(exc), "danger")
        return _render_auto_error(prompt_text, selected_model, 503)
    except AIResponseFormatError as exc:
        logger.warning("自动入学结果格式无效: {}", exc)
        flash(f"返回内容无法解析：{exc}", "danger")
        return _render_auto_error(prompt_text, selected_model, 502)
    except openai.APIConnectionError:
        logger.exception("自动入学服务连接失败")
        flash("自动安排服务暂时不可用，请稍后重试", "danger")
        return _render_auto_error(prompt_text, selected_model, 503)
    except openai.APIStatusError as exc:
        logger.exception("自动入学服务返回错误: status_code={}", exc.status_code)
        flash("自动安排服务返回错误，请稍后重试", "danger")
        return _render_auto_error(prompt_text, selected_model, 502)
    except (SCDBMySQLError, RuntimeError):
        logger.exception("自动入学保存时数据库访问失败")
        flash("入学安排保存失败，请检查 MySQL 连接配置后重试", "danger")
        return _render_auto_error(prompt_text, selected_model, 503)

    logger.success("自动入学安排成功: 数量={} 模型={}", result["save_summary"]["created"], result["model"])
    flash(f"已完成 {result['save_summary']['created']} 条入学安排", "success")
    context = _auto_page_context(
        prompt_text=result["prompt"],
        selected_model=result["model"],
        workflow_result=result,
    )
    return render_template("enrollment/auto.html", **context)
