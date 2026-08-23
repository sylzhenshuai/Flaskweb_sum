# alt_web01 · 大学生入学、毕业模拟系统（演示）

一个基于 **Flask** 的演示网站，用于模拟大学生入学、毕业的业务流程框架。
当前版本完成整体网站架构与页面骨架，各功能页面暂以页面名称占位展示。

## 功能结构

- **首页** — 网站欢迎页与功能入口
- **学生**
  - 手工添加学生 — ✅ 已实现：表单录入（姓名/性别/生日）、一键自动生成、保存到 MySQL，并通过 DataTables 展示最近保存的 1000 条记录、连续年龄及保存时间；生日范围 2000 ~ 2020 年
  - 批量添加学生（小数据量）
  - 批量添加学生（大数据量）
- **大学**
  - 手工添加大学
  - 手工添加专业组
  - 自动添加大学和专业组
- **入学**
  - 手动入学
  - 自动入学
- **统计分析**
  - 历年学生数量统计
  - 各大学学生数量统计

## 技术栈

| 项目 | 说明 |
| ---- | ---- |
| 语言 | Python ≥ 3.13 |
| Web 框架 | Flask ≥ 3.0（应用工厂模式） |
| 数据库 | MySQL + PyMySQL |
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
│       ├── templates/           # Jinja2 模板（base.html 导航框架）
│       └── static/css/          # 自定义样式
├── tests/                       # 预留测试目录
├── wsgi.py                      # WSGI 入口（gunicorn 加载点）
├── pyproject.toml               # PEP 621 项目元数据与构建配置
├── Dockerfile                   # 生产镜像定义
├── docker-compose.yml           # 容器编排
└── .dockerignore                # Docker 构建排除清单
```

## 本地运行

> 需要 Python ≥ 3.13。两个上游定制包（`random_student_info`、`sclog_lite`）
> 未发布到 PyPI，需先从 GitHub 安装（遵循 POC01 llms.txt 约定）。

```bash
pip install -r requirements.txt   # git 托管的上游包
pip install -e .                  # 本包（flask + pandas）
flask --app wsgi run --debug
```

浏览器访问 <http://127.0.0.1:5000>。

免安装快速预览（PowerShell，适用于已有 Flask 的环境）：

```powershell
$env:PYTHONPATH = "src"
flask --app wsgi run --debug
```

## Docker 部署

Web 容器通过外部 `app-network` 访问名为 `mysql-server` 的 MySQL 容器。
部署前复制 `.env.example` 为不会提交到 Git 的 `.env`，并填写实际的
`MYSQL_PASSWORD`。如果 MySQL 使用其他容器名或网络别名，还需修改
`MYSQL_HOST`。

```bash
cp .env.example .env
# 编辑 .env，填写真实的 MYSQL_PASSWORD 和 SECRET_KEY
docker compose up --build -d
```

浏览器访问 <http://localhost:15002>；停止服务：`docker compose down`。

## License

MIT
