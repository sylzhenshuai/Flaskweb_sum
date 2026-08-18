# alt_web01 生产镜像：基于官方 Python 3.13 slim 镜像
FROM python:3.13-slim

# 禁用字节码缓存并实时输出日志，便于容器内观察运行状态
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先复制元数据以利用镜像层缓存，再复制源码
COPY pyproject.toml README.md LICENSE ./
COPY wsgi.py ./
COPY src ./src

# 安装本包及部署依赖（gunicorn）
RUN pip install --no-cache-dir .[deploy]

EXPOSE 8000

# 容器内 WSGI 服务器启动命令
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "wsgi:app"]
