"""统计分析蓝图。

提供统计相关页面的路由：历年学生数量统计、各大学学生数量统计。
"""

from flask import Blueprint, render_template

bp = Blueprint("stats", __name__, url_prefix="/stats")


@bp.route("/yearly")
def yearly():
    """渲染"历年学生数量统计"页面。

    Returns:
        页面标题为"历年学生数量统计"的 HTML 页面。
    """
    return render_template("page.html", title="历年学生数量统计")


@bp.route("/by-university")
def by_university():
    """渲染"各大学学生数量统计"页面。

    Returns:
        页面标题为"各大学学生数量统计"的 HTML 页面。
    """
    return render_template("page.html", title="各大学学生数量统计")
