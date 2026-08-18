"""学生管理蓝图。

提供学生相关页面的路由：手工添加、批量添加（小数据量/大数据量）。
"""

from flask import Blueprint, render_template

bp = Blueprint("students", __name__, url_prefix="/students")


@bp.route("/add-manual")
def add_manual():
    """渲染"手工添加学生"页面。

    Returns:
        页面标题为"手工添加学生"的 HTML 页面。
    """
    return render_template("page.html", title="手工添加学生")


@bp.route("/add-bulk-small")
def add_bulk_small():
    """渲染"批量添加学生（小数据量）"页面。

    Returns:
        页面标题为"批量添加学生（小数据量）"的 HTML 页面。
    """
    return render_template("page.html", title="批量添加学生（小数据量）")


@bp.route("/add-bulk-large")
def add_bulk_large():
    """渲染"批量添加学生（大数据量）"页面。

    Returns:
        页面标题为"批量添加学生（大数据量）"的 HTML 页面。
    """
    return render_template("page.html", title="批量添加学生（大数据量）")
