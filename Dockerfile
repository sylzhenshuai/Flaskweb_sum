# alt_web01 生产镜像：基于官方 Python 3.13 slim 镜像
FROM python:3.13-slim

# Install git
RUN apt-get update && apt-get install -y git

# 禁用字节码缓存并实时输出日志，便于容器内观察运行状态
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先复制元数据以利用镜像层缓存，再复制源码
COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY wsgi.py ./
COPY src ./src

# 先装 git 托管的上游包（PyPI 未发布），再装本包及部署依赖（gunicorn）
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir .[deploy]

EXPOSE 8000

# 容器内 WSGI 服务器启动命令：
# - 直接调用包内工厂函数 create_app()，不依赖 /app/wsgi.py 与工作目录
# - --capture-output 捕获 worker 异常到主日志，避免真实报错被吞掉
CMD ["gunicorn", "--workers", "2", "--capture-output", "--bind", "0.0.0.0:8000", "alt_web01:create_app()"]
