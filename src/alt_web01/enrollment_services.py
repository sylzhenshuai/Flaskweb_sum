"""手动入学服务层。

负责入学记录表的初始化、候选项查询、入学安排和已安排清单查询。
"""

from __future__ import annotations

import datetime
from typing import TypedDict

from sedb_mysql import SCDBMySQL

from .services import _ensure_students_table, _prepared_database
from .university_services import _ensure_university_tables


class EnrollmentForm(TypedDict):
    """入学安排表单字段。"""

    student_id: int
    university_id: int
    major_group_id: int
    enrolled_on: str


class StoredEnrollment(EnrollmentForm):
    """供入学清单展示的已保存记录。"""

    id: int
    student_name: str
    student_gender: str
    university_name: str
    university_code: str
    major_group_name: str
    major_group_code: str
    saved_at: str


def _ensure_enrollment_tables(database: SCDBMySQL) -> None:
    """创建入学记录表及其依赖表。

    Args:
        database: 目标数据库客户端。
    """
    _ensure_students_table(database)
    _ensure_university_tables(database)
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS enrollment (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            student_id BIGINT UNSIGNED NOT NULL,
            university_id BIGINT UNSIGNED NOT NULL,
            major_group_id BIGINT UNSIGNED NOT NULL,
            enrolled_on DATE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_enrollment_student (student_id),
            KEY idx_enrollment_university (university_id),
            KEY idx_enrollment_major_group (major_group_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
        read_only=False,
    )


def _enrollment_database() -> SCDBMySQL:
    """返回完成入学相关建表检查的数据库客户端。"""
    return _prepared_database(_ensure_enrollment_tables)


def _parse_id(value: str, label: str) -> int:
    """解析表单中的正整数主键。

    Args:
        value: 表单传入的主键字符串。
        label: 字段中文名称。

    Returns:
        int: 解析后的正整数。

    Raises:
        ValueError: 值为空或不是正整数时抛出。
    """
    clean_value = value.strip()
    if not clean_value.isdigit() or int(clean_value) <= 0:
        raise ValueError(f"请选择有效的{label}")
    return int(clean_value)


def _normalize_enrollment(
    student_id: str,
    university_id: str,
    major_group_id: str,
    enrolled_on: str,
) -> EnrollmentForm:
    """校验并标准化入学安排字段。

    Args:
        student_id: 学生主键。
        university_id: 高校主键。
        major_group_id: 专业组主键。
        enrolled_on: 入学日期，ISO 格式。

    Returns:
        EnrollmentForm: 标准化后的入学字段。

    Raises:
        ValueError: 任一字段不合法时抛出。
    """
    clean_date = enrolled_on.strip() or datetime.date.today().isoformat()
    try:
        enrollment_date = datetime.date.fromisoformat(clean_date)
    except ValueError:
        raise ValueError("入学日期格式不正确，应为 YYYY-MM-DD") from None

    return EnrollmentForm(
        student_id=_parse_id(student_id, "学生"),
        university_id=_parse_id(university_id, "高校"),
        major_group_id=_parse_id(major_group_id, "专业组"),
        enrolled_on=enrollment_date.isoformat(),
    )


def _row_to_enrollment(row: dict[str, object]) -> StoredEnrollment:
    """将数据库行转换为入学记录字典。

    Args:
        row: 联表查询返回的数据库行。

    Returns:
        StoredEnrollment: 页面可直接使用的入学记录。
    """
    return StoredEnrollment(
        id=int(row["id"]),
        student_id=int(row["student_id"]),
        university_id=int(row["university_id"]),
        major_group_id=int(row["major_group_id"]),
        enrolled_on=str(row["enrolled_on"]),
        student_name=str(row["student_name"]),
        student_gender=str(row["student_gender"]),
        university_name=str(row["university_name"]),
        university_code=str(row["university_code"]),
        major_group_name=str(row["major_group_name"]),
        major_group_code=str(row["major_group_code"]),
        saved_at=str(row["saved_at"]),
    )


def _fetch_enrollment(database: SCDBMySQL, enrollment_id: int) -> StoredEnrollment:
    """按主键读取一条入学记录。"""
    row = database.fetchone(
        """
        SELECT e.id, e.student_id, e.university_id, e.major_group_id,
               e.enrolled_on,
               s.name AS student_name,
               s.gender AS student_gender,
               u.name AS university_name,
               u.code AS university_code,
               mg.name AS major_group_name,
               mg.code AS major_group_code,
               e.created_at AS saved_at
        FROM enrollment AS e
        INNER JOIN students AS s ON s.id = e.student_id
        INNER JOIN university AS u ON u.id = e.university_id
        INNER JOIN major_group AS mg ON mg.id = e.major_group_id
        WHERE e.id = %s
        """,
        (enrollment_id,),
    )
    if row is None:
        raise LookupError("未找到刚保存的入学记录")
    return _row_to_enrollment(row)


def create_enrollment(
    student_id: str,
    university_id: str,
    major_group_id: str,
    enrolled_on: str,
) -> StoredEnrollment:
    """校验并保存一条手动入学记录。

    Args:
        student_id: 学生主键字符串。
        university_id: 高校主键字符串。
        major_group_id: 专业组主键字符串。
        enrolled_on: 入学日期字符串。

    Returns:
        StoredEnrollment: 保存后的完整入学记录。

    Raises:
        ValueError: 选择项不存在、专业组不属于高校或学生已入学时抛出。
    """
    payload = _normalize_enrollment(
        student_id, university_id, major_group_id, enrolled_on
    )
    database = _enrollment_database()

    if database.fetchone(
        "SELECT id FROM students WHERE id = %s", (payload["student_id"],)
    ) is None:
        raise ValueError("请选择有效的学生")
    if database.fetchone(
        "SELECT id FROM university WHERE id = %s", (payload["university_id"],)
    ) is None:
        raise ValueError("请选择有效的高校")
    if database.fetchone(
        """
        SELECT id
        FROM major_group
        WHERE id = %s AND university_id = %s
        """,
        (payload["major_group_id"], payload["university_id"]),
    ) is None:
        raise ValueError("所选专业组不属于该高校")
    if database.fetchone(
        "SELECT id FROM enrollment WHERE student_id = %s",
        (payload["student_id"],),
    ) is not None:
        raise ValueError("该学生已经安排入学")

    database.insert("enrollment", dict(payload))
    row = database.fetchone(
        """
        SELECT id
        FROM enrollment
        WHERE student_id = %s AND university_id = %s AND major_group_id = %s
              AND enrolled_on = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            payload["student_id"],
            payload["university_id"],
            payload["major_group_id"],
            payload["enrolled_on"],
        ),
    )
    if row is None:
        raise LookupError("未找到刚保存的入学记录")
    return _fetch_enrollment(database, int(row["id"]))


def list_enrollments(limit: int = 1000) -> list[StoredEnrollment]:
    """返回最近安排入学的记录。

    Args:
        limit: 最多返回的记录数。

    Returns:
        list[StoredEnrollment]: 按入学日期、保存时间和主键升序排列的清单。

    Raises:
        ValueError: ``limit`` 不是正整数时抛出。
    """
    if limit <= 0:
        raise ValueError("limit 必须大于 0")

    database = _enrollment_database()
    rows = database.fetchall(
        """
        SELECT e.id, e.student_id, e.university_id, e.major_group_id,
               e.enrolled_on,
               s.name AS student_name,
               s.gender AS student_gender,
               u.name AS university_name,
               u.code AS university_code,
               mg.name AS major_group_name,
               mg.code AS major_group_code,
               e.created_at AS saved_at
        FROM enrollment AS e
        INNER JOIN students AS s ON s.id = e.student_id
        INNER JOIN university AS u ON u.id = e.university_id
        INNER JOIN major_group AS mg ON mg.id = e.major_group_id
        ORDER BY e.enrolled_on ASC, e.created_at ASC, e.id ASC
        LIMIT %s
        """,
        (limit,),
    )
    return [_row_to_enrollment(row) for row in rows]
