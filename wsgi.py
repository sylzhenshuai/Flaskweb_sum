"""WSGI 入口模块。

作为容器内 WSGI 服务器（gunicorn）的应用加载入口，
也可用于本地直接运行调试。

用法::

    gunicorn wsgi:app --bind 0.0.0.0:8000
    python wsgi.py            # 本地调试
"""

from dotenv import load_dotenv
from alt_web01 import create_app

load_dotenv()

#: 供 WSGI 服务器引用的全局应用对象
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
