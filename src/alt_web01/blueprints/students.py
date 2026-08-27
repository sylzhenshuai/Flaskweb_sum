"""学生管理蓝图。

"手工添加学生"提供完整闭环：表单录入、一键自动生成、保存
（写入 MySQL + 输出成功日志），并在页面下方展示已保存清单。
"""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sclog_lite import logger
from sedb_mysql import SCDBMySQLError
from werkzeug.wrappers import Response

from alt_web01.services import (
    add_student,
    generate_and_add_students,
    generate_student,
    list_students,
)

bp = Blueprint("students", __name__, url_prefix="/students")


@bp.get("/add-manual")
def add_manual() -> str:
    """渲染"手工添加学生"页面（表单 + 已保存清单）。

    Returns:
        str: 渲染后的页面 HTML。
    """
    try:
        students = list_students()
    except (SCDBMySQLError, RuntimeError):
        logger.exception("学生清单读取失败")
        flash("数据库暂时不可用，已显示空清单，请稍后刷新重试", "warning")
        # 页面本身保持可用；数据库恢复后刷新即可重新加载清单。
        students = []

    return render_template(
        "students/add_manual.html", title="手工添加学生", students=students
    )


@bp.post("/add-manual")
def save_student() -> Response:
    """保存手工录入的学生信息。

    校验通过后写入 MySQL 并输出保存成功日志，
    随后按 PRG 模式重定向回表单页；校验失败则 flash 提示后返回。

    Returns:
        Response: 重定向到手工添加页。
    """
    name = request.form.get("name", "")
    gender = request.form.get("gender", "")
    birthday = request.form.get("birthday", "")

    try:
        student = add_student(name, gender, birthday)
    except ValueError as exc:
        logger.warning(
            "学生保存失败: {} | 输入 name={!r} gender={!r} birthday={!r}",
            exc,
            name,
            gender,
            birthday,
        )
        flash(str(exc), "danger")
        return redirect(url_for("students.add_manual"))
    except (SCDBMySQLError, RuntimeError):
        logger.exception(
            "学生保存时数据库访问失败 | 输入 name={!r} gender={!r} birthday={!r}",
            name,
            gender,
            birthday,
        )
        flash("保存失败，请检查 MySQL 连接配置后重试", "danger")
        return redirect(url_for("students.add_manual"))

    logger.success(
        "学生保存成功: 姓名={} 性别={} 生日={}（已写入 MySQL）",
        student["name"],
        student["gender"],
        student["birthday"],
    )
    flash(f"学生「{student['name']}」保存成功", "success")
    return redirect(url_for("students.add_manual"))


@bp.get("/add-manual/random")
def random_student() -> Response:
    """自动生成一条随机学生信息（JSON API，供前端回填表单）。

    Returns:
        Response: JSON，含 name / gender / birthday 三个字段。
    """
    student = generate_student()
    logger.info(
        "自动生成学生信息: 姓名={} 性别={} 生日={}",
        student["name"],
        student["gender"],
        student["birthday"],
    )
    return jsonify(student)


def _bulk_page(
    *,
    title: str,
    mode: str,
    max_count: int,
) -> str:
    """渲染批量添加页面并加载最近学生清单。

    Args:
        title: 页面标题。
        mode: ``small`` 或 ``large``。
        max_count: 本页面允许的一次生成上限。

    Returns:
        str: 批量添加页面 HTML。
    """
    try:
        students = list_students()
    except (SCDBMySQLError, RuntimeError):
        logger.exception("批量添加页面读取学生清单失败")
        flash("数据库暂时不可用，清单将在恢复后重新加载", "warning")
        students = []

    return render_template(
        "students/add_bulk.html",
        title=title,
        mode=mode,
        max_count=max_count,
        students=students,
    )


def _save_bulk(*, mode: str, max_count: int) -> Response:
    """处理批量生成请求并按 PRG 模式返回页面。

    Args:
        mode: ``small`` 或 ``large``。
        max_count: 本页面允许的一次生成上限。

    Returns:
        Response: 重定向到对应批量添加页面。
    """
    raw_count = request.form.get("count", "")
    try:
        count = int(raw_count)
    except ValueError:
        count = 0

    if not 1 <= count <= max_count:
        flash(f"请输入 1 至 {max_count} 之间的整数", "danger")
        return redirect(request.path)

    try:
        records = generate_and_add_students(count)
    except (SCDBMySQLError, RuntimeError):
        logger.exception("批量添加学生时数据库访问失败 | 数量={}", count)
        flash("批量保存失败，请检查 MySQL 连接配置后重试", "danger")
        return redirect(request.path)
    except ValueError as exc:
        logger.warning("批量生成学生失败: {}", exc)
        flash(str(exc), "danger")
        return redirect(request.path)

    logger.success("批量添加学生成功: 模式={} 数量={}", mode, len(records))
    flash(f"已生成并保存 {len(records)} 名学生", "success")
    return redirect(request.path)


@bp.route("/add-bulk-small", methods=["GET", "POST"])
def add_bulk_small() -> str | Response:
    """渲染或处理小数量批量添加页面。"""
    if request.method == "POST":
        return _save_bulk(mode="small", max_count=100)
    return _bulk_page(title="批量添加学生（小数量）", mode="small", max_count=100)


@bp.route("/add-bulk-large", methods=["GET", "POST"])
def add_bulk_large() -> str | Response:
    """渲染或处理大数量批量添加页面。"""
    if request.method == "POST":
        return _save_bulk(mode="large", max_count=10000)
    return _bulk_page(title="批量添加学生（大数量）", mode="large", max_count=10000)
