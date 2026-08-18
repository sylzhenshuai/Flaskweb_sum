"""首页蓝图。"""

from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    """渲染网站首页。

    Returns:
        首页 HTML 页面。
    """
    return render_template("index.html", title="首页")
