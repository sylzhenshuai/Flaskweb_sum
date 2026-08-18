"""alt_web01 应用工厂包。

本包实现"大学生入学、毕业模拟系统"演示网站，遵循 Flask 官方推荐的
工厂模式（Application Factory Pattern）与 src 布局（PEP 517/621）。
"""

from flask import Flask

from .blueprints import ALL_BLUEPRINTS


def create_app():
    """创建并配置 Flask 应用实例。

    工厂函数：实例化应用、注册全部蓝图，返回可直接交给
    WSGI 服务器（如 gunicorn）使用的应用对象。

    Returns:
        Flask: 完成初始化与蓝图注册的 Flask 应用实例。
    """
    app = Flask(__name__)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app
