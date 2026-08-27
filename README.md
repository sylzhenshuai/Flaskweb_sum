# alt_web01 · 大学生入学、毕业模拟系统（演示）

一个基于 **Flask** 的演示网站，用于模拟大学生入学、毕业的业务流程框架。
当前版本已经完成学生、高校与专业组的手工录入、手动入学和学生批量录入闭环，其余模块保留页面骨架并逐步接入。

## 功能结构

- **首页** — 网站欢迎页与功能入口
- **学生**
  - 手工添加学生 — ✅ 已实现：表单录入（姓名/性别/生日）、一键自动生成、保存到 MySQL，并通过 DataTables 展示最近保存的 1000 条记录、连续年龄及保存时间；生日范围 2000 ~ 2020 年
  - 批量添加学生（小数量） — ✅ 已实现：使用 `random_student_info` 生成并批量保存 1~100 名学生
  - 批量添加学生（大数量） — ✅ 已实现：使用 `random_student_info` 生成并分批保存 1~10000 名学生
- **大学**
  - 手工添加大学 — ✅ 已实现：录入高校名称、三位数字高校代码、办学类型与高校层次，保存到 MySQL，并通过 DataTables 展示全部已保存高校；支持点击名称或代码回填后覆盖修改；高校名称和代码全局唯一
  - 手工添加专业组 — ✅ 已实现：选择已存在高校后录入专业组名称与代码，保存到 MySQL，并通过 DataTables 展示当前高校下全部专业组；切换高校时自动切换清单；支持点击名称或代码回填后覆盖修改；同校内名称和代码唯一
  - 自动添加大学和专业组 — ✅ 已实现：通过自然语言描述高校与专业组，调用 OpenAI-compatible AI 服务自动解析并复用现有保存逻辑写入 MySQL；已存在记录会按名称或代码匹配后覆盖更新
- **入学**
  - 手动入学 — ✅ 已实现：通过学生、高校、专业组候选项安排入学，支持模糊输入、日期和分页清单
  - 自动入学 — ✅ 已实现：通过自然语言解析已有学生、高校与专业组，批量写入与手动入学共用的入学记录表
- **统计分析**
  - 历年学生数量统计
  - 各大学学生数量统计

## 技术栈

| 项目 | 说明 |
| ---- | ---- |
| 语言 | Python ≥ 3.13 |
| Web 框架 | Flask ≥ 3.0（应用工厂模式） |
| 数据库 | MySQL + sedb_mysql（mysqlclient + 有界连接池） |
| 前端 | Bootstrap 5.3（CDN）+ 自定义清新配色样式 |
| 打包 | PEP 517 / PEP 621（src 布局 + pyproject.toml） |
| 部署 | Docker + gunicorn |

## 目录结构

```
Flaskweb_sum/
├── src/
│   └── alt_web01/
│       ├── __init__.py          # create_app() 应用工厂
│       ├── blueprints/          # 各功能蓝图（路由）
│       │   ├── main.py          # 首页
│       │   ├── students.py      # 学生
│       │   ├── universities.py  # 大学
│       │   ├── enrollment.py    # 入学
│       │   └── stats.py         # 统计分析
│       ├── enrollment_services.py # 入学记录服务
│       ├── enrollment_ai_services.py # 自动入学解析与保存服务
│       ├── services.py           # 学生与随机生成服务
│       ├── university_services.py # 高校与专业组服务
│       ├── templates/           # Jinja2 模板（base.html 导航框架）
│       │   ├── students/        # 学生模块模板
│       │   ├── enrollment/      # 入学模块模板
│       │   └── universities/    # 高校与专业组模块模板
│       └── static/css/          # 自定义样式
├── tests/                       # 预留测试目录
├── wsgi.py                      # WSGI 入口（gunicorn 加载点）
├── pyproject.toml               # PEP 621 项目元数据与构建配置
├── Dockerfile                   # 生产镜像定义
├── docker-compose.yml           # 容器编排
└── .dockerignore                # Docker 构建排除清单
```

## 本地运行

> 需要 Python ≥ 3.13。三个上游定制包（`sedb_mysql`、`random_student_info`、`sclog_lite`）
> 未发布到 PyPI，使用 `requirements.txt` 中固定 tag 的原始 GitHub 仓库 URL 安装。

```bash
python -m pip install -r requirements.txt  # 原始 Git URL 固定 tag 的上游包
python -m pip install -e .                 # 本包及运行依赖
python -m flask --app wsgi run --debug
```

浏览器访问 <http://127.0.0.1:5000>。

若要使用“自动添加大学和专业组”或“自动入学”，还需要在运行环境中配置 AI 密钥环境变量 `API_KEY_GJLD`。当前项目默认通过 OpenAI-compatible SDK 调用 `https://api.siliconflow.cn/v1`，默认模型为 `deepseek-ai/DeepSeek-V4-Flash`；也可通过 `SILICONFLOW_BASE_URL` 与 `SILICONFLOW_MODEL` 覆盖。

Windows 直接运行前，在项目根目录创建本机 `.env`，将 `MYSQL_HOST` 改为
MySQL 虚拟机 IP，并填写实际密码；`python-dotenv` 会在启动时自动读取它：

```powershell
Copy-Item .env.example .env
# 编辑 .env 后运行：
python -m flask --app wsgi run --debug
```

## Docker 部署

Web 容器通过外部 `app-network` 访问名为 `mysql-server` 的 MySQL 容器。
首次克隆或以后更新都使用同一个入口：

```bash
bash update.sh
```

首次运行时脚本会隐藏式询问 `test_user` 的 MySQL 密码，在虚拟机本地创建
权限为 `600` 的 `.env`、生成随机 `SECRET_KEY`，然后校验、构建并启动服务。
`.env` 不进入 Git；后续执行 `bash update.sh` 不会再次询问。如果 MySQL 使用
其他容器名或网络别名，再修改本机 `.env` 中的 `MYSQL_HOST`。

这里必须输入 `MYSQL_USER=test_user` 对应的 `MYSQL_PASSWORD`，不要输入
`MYSQL_ROOT_PASSWORD`。由于 `.env` 被 Git 忽略，`git pull` 不会创建、覆盖或
修正虚拟机中已有的 `.env`。如果曾经输错密码，直接修改本机配置并重新创建
Web 容器，无需删除或重新克隆仓库：

```bash
nano .env
docker compose up -d --force-recreate web
```

浏览器访问 <http://localhost:15002>；停止服务：`docker compose down`。

## License

MIT
