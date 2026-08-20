"""学生管理蓝图。

"手工添加学生"提供完整闭环：表单录入、一键自动生成、保存
（写内存清单 + 输出成功日志），并在页面下方展示已保存清单。
"""

from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sclog_lite import logger

from alt_web01.services import add_student, generate_student, list_students

bp = Blueprint("students", __name__, url_prefix="/students")


@bp.get("/add-manual")
def add_manual() -> str:
    """渲染"手工添加学生"页面（表单 + 已保存清单）。

    Returns:
        str: 渲染后的页面 HTML。
    """
    return render_template(
        "students/add_manual.html",
        title="手工添加学生",
        students=list_students(),
    )


@bp.post("/add-manual")
def save_student() -> Response:
    """保存手工录入的学生信息。

    校验通过后写入内存清单并输出保存成功日志（暂不写入数据库），
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

    logger.success(
        "学生保存成功: 姓名={} 性别={} 生日={}（内存清单共 {} 条）",
        student["name"],
        student["gender"],
        student["birthday"],
        len(list_students()),
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


@bp.route("/add-bulk-small")
def add_bulk_small() -> str:
    """渲染"批量添加学生（小数据量）"页面。

    Returns:
        str: 页面标题为"批量添加学生（小数据量）"的 HTML 页面。
    """
    return render_template("page.html", title="批量添加学生（小数据量）")


@bp.route("/add-bulk-large")
def add_bulk_large() -> str:
    """渲染"批量添加学生（大数据量）"页面。

    Returns:
        str: 页面标题为"批量添加学生（大数据量）"的 HTML 页面。
    """
    return render_template("page.html", title="批量添加学生（大数据量）")
