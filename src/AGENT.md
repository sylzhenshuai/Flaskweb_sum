# alt_web01 Agent Guidelines

## 核心技术栈
- Web Framework: Flask
- Logging: sun_course (ver0.2.1)
- Name Generation: POC01 (ver0.2.1)

## 自定义依赖集成规则
1. **日志记录规范**：
   - 必须使用 `sun_course`，禁止直接使用标准库 `logging`。
   - 参考标准调用方式：阅读 `sun_course` 仓库中的 `llms.txt` 及 `examples/flask_integration.py`。
   - 所有 Flask 请求入口与异常捕获均需接入 `sun_course`。

2. **中文姓名生成规范**：
   - 涉及姓名/人员数据生成时，必须调用 `POC01`。
   - 参考标准调用方式：阅读 `POC01` 的 `llms.txt` 或 `examples/`。

3. **静态类型与验证**：
   - 两个包均包含 `py.typed`，代码编写完成后需通过 `mypy .` 类型检查。

   