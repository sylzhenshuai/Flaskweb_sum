"""alt_web01 应用工厂包。

本包实现"大学生入学、毕业模拟系统"演示网站，遵循 Flask 官方推荐的
工厂模式（Application Factory Pattern）与 src 布局（PEP 517/621）。
日志基于上游 ``sclog_lite`` 包（loguru 封装）配置。
"""

from __future__ import annotations

import os
import sys
import time

from flask import Flask, Response, request
from sclog_lite import logger

from .blueprints import ALL_BLUEPRINTS

#: 控制台与文件 sink 统一在首次 create_app 时配置，避免重复输出。
_logging_configured = False
#: 文件日志 sink 句柄；进程内全局唯一，避免重复 create_app 时日志翻倍
_file_sink_id: int | None = None


def _configure_logging(app: Flask) -> None:
    """按照上游 sclog_lite 规范配置应用日志中间件。

    遵循 POC01 ``llms.txt`` 中 ``setup_logger()`` 的模式：先注册文件
    sink（日志写入运行目录 ``logs/``，由 sclog_lite 自动创建），再通过
    before/after request 钩子逐请求记录访问日志。

    Args:
        app: 目标 Flask 应用实例。
    """
    global _file_sink_id, _logging_configured
    if not _logging_configured:
        logger.remove()
        logger.add(
            sys.stderr,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            colorize=False,
        )
        _file_sink_id = logger.add_file_sink(
            rotation="10 MB",
            retention=5,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        )
        _logging_configured = True

    @app.before_request
    def _log_request_start() -> None:
        """请求开始时打点计时（日志中间件·前置）。"""
        request.environ["alt_web01.start_ts"] = time.perf_counter()

    @app.after_request
    def _log_request_end(response: Response) -> Response:
        """请求结束时输出一行访问日志（日志中间件·后置）。

        Args:
            response: Flask 响应对象，原样返回。

        Returns:
            Response: 未修改的响应对象。
        """
        start = request.environ.get("alt_web01.start_ts")
        elapsed_ms = (
            (time.perf_counter() - float(start)) * 1000 if start else 0.0
        )
        logger.info(
            "{} {} -> {} ({:.1f} ms)",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def create_app() -> Flask:
    """创建并配置 Flask 应用实例。

    Returns:
        Flask: 完成日志配置与蓝图注册的 Flask 应用实例。
    """
    app = Flask(__name__)
    app.secret_key = os.getenv(
        "SECRET_KEY", "alt_web01-secret-key-change-in-production"
    )
    _configure_logging(app)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app
