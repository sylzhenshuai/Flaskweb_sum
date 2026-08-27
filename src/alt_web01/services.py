"""学生信息服务层：随机生成与 MySQL 持久化。

生成引擎遵循上游规范（POC01 ``llms.txt``）：随机学生信息由
``random_student_info.generate`` 产生；生日范围按业务需求约束为
2000-01-01 ~ 2020-12-31。学生记录通过 ``sedb_mysql`` 连接池写入 MySQL。
"""

from __future__ import annotations

import atexit
import datetime
import os
from collections.abc import Callable, Iterable, Mapping
from functools import cache
from typing import TypedDict, cast

from random_student_info import generate
from sedb_mysql import ConnectionError as DatabaseConnectionError
from sedb_mysql import MySQLData, PoolConfig, SCDBMySQL

#: 生日允许范围（含端点）
BIRTH_START = datetime.date(2000, 1, 1)
BIRTH_END = datetime.date(2020, 12, 31)


class Student(TypedDict):
    """学生记录。

    Attributes:
        name: 姓名。
        gender: 性别，"男" 或 "女"。
        birthday: 生日，ISO 格式 "YYYY-MM-DD"。
    """

    name: str
    gender: str
    birthday: str


class StoredStudent(Student):
    """供清单展示的已持久化学生记录。"""

    id: int
    age: float
    saved_at: str


def _student_from_row(row: Mapping[str, object]) -> Student:
    """将生成器 DataFrame 的一行转换为统一学生记录。

    Args:
        row: 包含中文列名的生成器行对象。

    Returns:
        Student: 可写入学生表的标准化记录。
    """
    birthday = row["生日"]
    return Student(
        name=str(row["姓名"]),
        gender=str(row["性别"]),
        birthday=getattr(birthday, "strftime")("%Y-%m-%d"),
    )


@cache
def _database() -> SCDBMySQL:
    """按进程创建一个有界连接池，并从环境变量读取 MySQL 配置。"""
    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError:
        raise RuntimeError("MYSQL_PORT 必须为整数") from None

    return SCDBMySQL(
        MySQLData(
            host=os.getenv("MYSQL_HOST", "mysql"),
            port=port,
            user=os.getenv("MYSQL_USER", "test_user"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "test_db"),
            charset="utf8mb4",
            connect_timeout=5,
        ),
        # ponytail: 2 个 Gunicorn worker 合计最多 20 条连接；有指标后再参数化。
        PoolConfig(
            mincached=0,
            maxcached=5,
            maxconnections=10,
            checkout_timeout=5,
        ),
    )


def _close_database() -> None:
    """进程退出时关闭已创建连接池中的空闲连接。"""
    _discard_cached_database()


def _discard_cached_database() -> None:
    """丢弃当前缓存的数据库客户端，供下一次请求重建。"""
    if not _database.cache_info().currsize:
        return

    database = _database()
    _database.cache_clear()
    try:
        database.close()
    except Exception:
        # 保留原始连接错误；损坏连接的清理失败不应覆盖主故障。
        pass


def _prepared_database(setup: Callable[[SCDBMySQL], None] | None = None) -> SCDBMySQL:
    """确保数据库客户端可用，并在首次连库失败时重建一次。

    Args:
        setup: 在返回数据库客户端前执行的建表或预热回调。

    Returns:
        SCDBMySQL: 已完成一次可恢复预热检查的数据库客户端。
    """
    database = _database()
    try:
        if setup is not None:
            setup(database)
    except DatabaseConnectionError:
        _discard_cached_database()
        database = _database()
        if setup is not None:
            setup(database)
    return database


atexit.register(_close_database)


def _ensure_students_table(database: SCDBMySQL) -> None:
    """创建尚不存在的学生表。"""
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(30) NOT NULL,
            gender ENUM('男', '女') NOT NULL,
            birthday DATE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
        read_only=False,
    )


def generate_student() -> Student:
    """自动生成一条随机学生信息（生日限定 2000~2020 年）。

    Returns:
        Student: 包含姓名、性别、生日的学生字典。
    """
    frame = generate(1, birth_start=BIRTH_START, birth_end=BIRTH_END)
    return _student_from_row(cast(Mapping[str, object], frame.iloc[0]))


def generate_students(count: int) -> list[Student]:
    """使用 ``random_student_info`` 生成一批学生记录。

    Args:
        count: 生成数量，必须为正整数。

    Returns:
        list[Student]: 包含姓名、性别和生日的学生记录。

    Raises:
        ValueError: ``count`` 不是正整数时抛出。
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("生成数量必须为正整数")

    frame = generate(count, birth_start=BIRTH_START, birth_end=BIRTH_END)
    return [
        _student_from_row(cast(Mapping[str, object], row))
        for _, row in frame.iterrows()
    ]


def add_students(students: Iterable[Student]) -> int:
    """将一批学生记录写入 MySQL。

    Args:
        students: 待保存的学生记录迭代器。

    Returns:
        int: 实际写入的记录数。
    """
    records = list(students)
    if not records:
        return 0

    database = _prepared_database(_ensure_students_table)
    return database.bulk_insert(
        "students",
        [dict(student) for student in records],
        batch_size=1000,
    )


def generate_and_add_students(count: int) -> list[Student]:
    """生成并保存一批学生，供批量录入页面调用。

    Args:
        count: 生成数量，必须为正整数。

    Returns:
        list[Student]: 本次生成并保存的学生记录。
    """
    records = generate_students(count)
    add_students(records)
    return records


def add_student(name: str, gender: str, birthday: str) -> Student:
    """校验并保存一条学生信息到 MySQL。

    Args:
        name: 姓名，去除首尾空白后须为 1~30 个字符。
        gender: 性别，仅接受 "男" 或 "女"。
        birthday: 生日字符串，"YYYY-MM-DD" 格式，
            须在 2000-01-01 至 2020-12-31 之间。

    Returns:
        Student: 保存后的学生记录。

    Raises:
        ValueError: 任一字段校验失败时抛出，消息为可读中文。
    """
    name = name.strip()
    if not name or len(name) > 30:
        raise ValueError("姓名不能为空，且不超过 30 个字符")

    if gender not in ("男", "女"):
        raise ValueError("性别必须为“男”或“女”")

    try:
        day = datetime.date.fromisoformat(birthday.strip())
    except ValueError:
        raise ValueError("生日格式不正确，应为 YYYY-MM-DD") from None
    if not BIRTH_START <= day <= BIRTH_END:
        raise ValueError("生日必须在 2000-01-01 至 2020-12-31 之间")

    student = Student(name=name, gender=gender, birthday=day.isoformat())
    database = _prepared_database(_ensure_students_table)
    database.insert("students", student)
    return student


def list_students() -> list[StoredStudent]:
    """从 MySQL 返回最近保存的 1000 条学生记录。

    Returns:
        list[StoredStudent]: 按保存时间和主键升序排列的学生记录列表；
            年龄按查询当天的连续年龄计算并保留一位小数。
    """
    database = _prepared_database(_ensure_students_table)
    rows = database.fetchall(
        """
        SELECT id, name, gender, birthday,
               ROUND(DATEDIFF(CURDATE(), birthday) / 365.2425, 1) AS age,
               created_at AS saved_at
        FROM students
         ORDER BY created_at ASC, id ASC
        LIMIT 1000
        """
    )

    return [
        StoredStudent(
            id=int(row["id"]),
            name=str(row["name"]),
            gender=str(row["gender"]),
            birthday=str(row["birthday"]),
            age=float(row["age"]),
            saved_at=str(row["saved_at"]),
        )
        for row in rows
    ]
