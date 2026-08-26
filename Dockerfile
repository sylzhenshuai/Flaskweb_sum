# alt_web01 生产镜像：基于官方 Python 3.13 slim 镜像
FROM python:3.13-slim

# Git 用于安装 VCS 依赖；其余软件包用于在 Debian slim 中编译 mysqlclient。
# ponytail: 先保留单阶段构建；只有镜像体积成为瓶颈时再改 multi-stage。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        git \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 禁用字节码缓存并实时输出日志，便于容器内观察运行状态
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先复制元数据以利用镜像层缓存，再复制源码
COPY pyproject.toml README.md LICENSE ./
COPY wsgi.py ./
COPY src ./src

# 安装本包、固定 tag 的上游包及部署依赖（gunicorn）
RUN pip install --no-cache-dir .[deploy]

EXPOSE 8000

# 容器内 WSGI 服务器启动命令：
# - 直接调用包内工厂函数 create_app()，不依赖 /app/wsgi.py 与工作目录
# - --capture-output 捕获 worker 异常到主日志，避免真实报错被吞掉
CMD ["gunicorn", "--workers", "2", "--capture-output", "--bind", "0.0.0.0:8000", "alt_web01:create_app()"]
