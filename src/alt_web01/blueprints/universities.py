"""大学管理蓝图。

提供大学与专业组相关页面的路由：手工添加大学、
手工添加专业组、自动添加大学和专业组。
"""

from flask import Blueprint, render_template

bp = Blueprint("universities", __name__, url_prefix="/universities")


@bp.route("/add-manual")
def add_manual():
    """渲染"手工添加大学"页面。

    Returns:
        页面标题为"手工添加大学"的 HTML 页面。
    """
    return render_template("page.html", title="手工添加大学")


@bp.route("/add-major-group")
def add_major_group():
    """渲染"手工添加专业组"页面。

    Returns:
        页面标题为"手工添加专业组"的 HTML 页面。
    """
    return render_template("page.html", title="手工添加专业组")


@bp.route("/add-auto")
def add_auto():
    """渲染"自动添加大学和专业组"页面。

    Returns:
        页面标题为"自动添加大学和专业组"的 HTML 页面。
    """
    return render_template("page.html", title="自动添加大学和专业组")
