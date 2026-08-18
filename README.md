# alt_web01 · 大学生入学、毕业模拟系统（演示）

一个基于 **Flask** 的演示网站，用于模拟大学生入学、毕业的业务流程框架。
当前版本完成整体网站架构与页面骨架，各功能页面暂以页面名称占位展示。

## 功能结构

- **首页** — 网站欢迎页与功能入口
- **学生**
  - 手工添加学生
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

> 需要 Python ≥ 3.13（当前仅依赖 Flask，无需数据库）。

```bash
pip install -e .
flask --app wsgi run --debug
```

浏览器访问 <http://127.0.0.1:5000>。

免安装快速预览（PowerShell，适用于已有 Flask 的环境）：

```powershell
$env:PYTHONPATH = "src"
flask --app wsgi run --debug
```

## Docker 部署

```bash
docker compose up --build -d
```

浏览器访问 <http://localhost:15002>；停止服务：`docker compose down`。

## License

MIT
