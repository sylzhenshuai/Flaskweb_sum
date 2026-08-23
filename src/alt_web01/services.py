"""学生信息服务层：随机生成与 MySQL 持久化。

生成引擎遵循上游规范（POC01 ``llms.txt``）：随机学生信息由
``random_student_info.generate`` 产生；生日范围按业务需求约束为
2000-01-01 ~ 2020-12-31。学生记录通过 PyMySQL 写入 MySQL。
"""

from __future__ import annotations

import datetime
import os
from typing import TypedDict

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor, DictCursor
from random_student_info import generate

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


def _connect() -> Connection[DictCursor]:
    """使用容器环境变量连接 MySQL。"""
    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError:
        raise RuntimeError("MYSQL_PORT 必须为整数") from None

    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=port,
        user=os.getenv("MYSQL_USER", "test_user"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "test_db"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=5,
    )


def _ensure_students_table(cursor: Cursor) -> None:
    """创建尚不存在的学生表。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(30) NOT NULL,
            gender ENUM('男', '女') NOT NULL,
            birthday DATE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )


def generate_student() -> Student:
    """自动生成一条随机学生信息（生日限定 2000~2020 年）。

    Returns:
        Student: 包含姓名、性别、生日的学生字典。
    """
    df = generate(1, birth_start=BIRTH_START, birth_end=BIRTH_END)
    row = df.iloc[0]
    return Student(
        name=str(row["姓名"]),
        gender=str(row["性别"]),
        birthday=row["生日"].strftime("%Y-%m-%d"),
    )


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
    with _connect() as connection:
        with connection.cursor() as cursor:
            _ensure_students_table(cursor)
            cursor.execute(
                "INSERT INTO students (name, gender, birthday) VALUES (%s, %s, %s)",
                (student["name"], student["gender"], student["birthday"]),
            )
        connection.commit()
    return student


def list_students() -> list[StoredStudent]:
    """从 MySQL 返回最近保存的 1000 条学生记录。

    Returns:
        list[StoredStudent]: 按保存时间和主键降序排列的学生记录列表；
            年龄按查询当天的连续年龄计算并保留一位小数。
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            _ensure_students_table(cursor)
            cursor.execute(
                """
                SELECT id, name, gender, birthday,
                       ROUND(DATEDIFF(CURDATE(), birthday) / 365.2425, 1) AS age,
                       created_at AS saved_at
                FROM students
                ORDER BY created_at DESC, id DESC
                LIMIT 1000
                """
            )
            rows = cursor.fetchall()

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
