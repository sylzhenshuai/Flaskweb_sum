"""入学管理蓝图。

提供入学流程相关页面的路由：手动入学、自动入学。
"""

from flask import Blueprint, render_template

bp = Blueprint("enrollment", __name__, url_prefix="/enrollment")


@bp.route("/manual")
def manual():
    """渲染"手动入学"页面。

    Returns:
        页面标题为"手动入学"的 HTML 页面。
    """
    return render_template("page.html", title="手动入学")


@bp.route("/auto")
def auto():
    """渲染"自动入学"页面。

    Returns:
        页面标题为"自动入学"的 HTML 页面。
    """
    return render_template("page.html", title="自动入学")
