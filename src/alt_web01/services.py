"""学生信息服务层：随机生成与内存存储。

生成引擎遵循上游规范（POC01 ``llms.txt``）：随机学生信息由
``random_student_info.generate`` 产生；生日范围按业务需求约束为
2000-01-01 ~ 2020-12-31。存储暂用进程内存清单，不写入数据库。
"""

from __future__ import annotations

import datetime
import threading
from typing import TypedDict

from random_student_info import generate

#: 生日允许范围（含端点）
BIRTH_START = datetime.date(2000, 1, 1)
BIRTH_END = datetime.date(2020, 12, 31)


class Student(TypedDict):
    """学生记录（内存态）。

    Attributes:
        name: 姓名。
        gender: 性别，"男" 或 "女"。
        birthday: 生日，ISO 格式 "YYYY-MM-DD"。
    """

    name: str
    gender: str
    birthday: str


_lock = threading.Lock()
_students: list[Student] = []


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
    """校验并保存一条学生信息到内存清单。

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
    with _lock:
        _students.append(student)
    return student


def list_students() -> list[Student]:
    """返回已保存学生清单的副本。

    Returns:
        list[Student]: 按保存先后排列的学生记录列表。
    """
    with _lock:
        return list(_students)
