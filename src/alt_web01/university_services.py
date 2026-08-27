"""大学与专业组服务层：校验、持久化与清单查询。

大学与专业组遵循与学生模块一致的模式：先做字段校验与重复性检查，
再通过 ``sedb_mysql`` 持久化到 MySQL，并把结果列表返回给页面层。
"""

from __future__ import annotations

import re
from typing import TypedDict

from sedb_mysql import SCDBMySQL

from .services import _prepared_database

UNIVERSITY_TYPES = ("民办", "公办")
UNIVERSITY_NATURES = ("985", "211", "一本", "其他")
UNIVERSITY_NAME_MAX_LENGTH = 120
MAJOR_GROUP_NAME_MAX_LENGTH = 120
_UNIVERSITY_CODE_PATTERN = re.compile(r"^\d{3}$")
_MAJOR_GROUP_CODE_PATTERN = re.compile(r"^\d{1,6}$")


class UniversityForm(TypedDict):
    """高校录入表单。"""

    name: str
    code: str
    type: str
    nature: str


class StoredUniversity(UniversityForm):
    """用于清单展示的高校记录。"""

    id: int
    saved_at: str


class MajorGroupForm(TypedDict):
    """专业组录入表单。"""

    university_id: int
    name: str
    code: str


class StoredMajorGroup(MajorGroupForm):
    """用于清单展示的专业组记录。"""

    id: int
    university_name: str
    university_code: str
    saved_at: str


class UniversityCatalogSummary(TypedDict):
    """高校模块概览统计。"""

    total_universities: int
    total_major_groups: int


def list_recent_major_groups(limit: int = 1000) -> list[StoredMajorGroup]:
    """返回跨全部高校的专业组清单。

    Args:
        limit: 最多返回的记录数。

    Returns:
        list[StoredMajorGroup]: 按保存时间与主键升序排列的专业组清单。
    """
    if limit <= 0:
        raise ValueError("limit 必须大于 0")

    database = _university_database()
    rows = database.fetchall(
        """
        SELECT mg.id, mg.university_id, mg.name, mg.code,
               u.name AS university_name,
               u.code AS university_code,
               mg.created_at AS saved_at
        FROM major_group AS mg
        INNER JOIN university AS u ON u.id = mg.university_id
        ORDER BY mg.created_at ASC, mg.id ASC
        LIMIT %s
        """,
        (limit,),
    )
    return [
        StoredMajorGroup(
            id=int(row["id"]),
            university_id=int(row["university_id"]),
            name=str(row["name"]),
            code=str(row["code"]),
            university_name=str(row["university_name"]),
            university_code=str(row["university_code"]),
            saved_at=str(row["saved_at"]),
        )
        for row in rows
    ]


def _ensure_university_tables(database: SCDBMySQL) -> None:
    """创建高校与专业组表。

    Args:
        database: 目标数据库客户端。
    """
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS university (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            code CHAR(3) NOT NULL,
            school_type ENUM('民办', '公办') NOT NULL,
            school_nature ENUM('985', '211', '一本', '其他') NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_university_name (name),
            UNIQUE KEY uq_university_code (code)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
        read_only=False,
    )
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS major_group (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            university_id BIGINT UNSIGNED NOT NULL,
            name VARCHAR(120) NOT NULL,
            code VARCHAR(6) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_major_group_name (university_id, name),
            UNIQUE KEY uq_major_group_code (university_id, code),
            KEY idx_major_group_university (university_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """,
        read_only=False,
    )


def _university_database() -> SCDBMySQL:
    """返回完成高校相关建表检查的数据库客户端。

    Returns:
        SCDBMySQL: 可用于高校模块的数据库客户端。
    """
    return _prepared_database(_ensure_university_tables)


def _normalize_university(
    name: str,
    code: str,
    school_type: str,
    nature: str,
) -> UniversityForm:
    """校验并标准化高校字段。

    Args:
        name: 高校名称。
        code: 三位数字高校代码。
        school_type: 高校办学类型。
        nature: 高校层次。

    Returns:
        UniversityForm: 标准化后的高校信息。

    Raises:
        ValueError: 任一字段不合法时抛出。
    """
    clean_name = name.strip()
    clean_code = code.strip()
    clean_type = school_type.strip()
    clean_nature = nature.strip()

    if not clean_name or len(clean_name) > UNIVERSITY_NAME_MAX_LENGTH:
        raise ValueError("高校名称不能为空，且不超过 120 个字符")
    if not _UNIVERSITY_CODE_PATTERN.fullmatch(clean_code):
        raise ValueError("高校代码必须为 3 位数字")
    if clean_type not in UNIVERSITY_TYPES:
        raise ValueError("高校类型必须为“民办”或“公办”")
    if clean_nature not in UNIVERSITY_NATURES:
        raise ValueError("高校层次必须为 985、211、一本或其他")

    return UniversityForm(
        name=clean_name,
        code=clean_code,
        type=clean_type,
        nature=clean_nature,
    )


def _normalize_major_group(
    university_id: str,
    name: str,
    code: str,
) -> MajorGroupForm:
    """校验并标准化专业组字段。

    Args:
        university_id: 所属高校 ID 字符串。
        name: 专业组名称。
        code: 专业组代码。

    Returns:
        MajorGroupForm: 标准化后的专业组信息。

    Raises:
        ValueError: 任一字段不合法时抛出。
    """
    clean_name = name.strip()
    clean_code = code.strip()
    if not university_id or not str(university_id).isdigit():
        raise ValueError("请选择所属高校")
    if not clean_name or len(clean_name) > MAJOR_GROUP_NAME_MAX_LENGTH:
        raise ValueError("专业组名称不能为空，且不超过 120 个字符")
    if not _MAJOR_GROUP_CODE_PATTERN.fullmatch(clean_code):
        raise ValueError("专业组代码必须为 1 至 6 位数字")

    return MajorGroupForm(
        university_id=int(university_id),
        name=clean_name,
        code=clean_code,
    )


def _parse_record_id(record_id: str) -> int | None:
    """解析可选的记录 ID。

    Args:
        record_id: 来自表单的隐藏主键字段。

    Returns:
        int | None: 空值返回 None，否则返回正整数主键。

    Raises:
        ValueError: 传入值不是正整数时抛出。
    """
    clean_id = record_id.strip()
    if not clean_id:
        return None
    if not clean_id.isdigit():
        raise ValueError("记录标识不合法，请刷新页面后重试")
    return int(clean_id)


def _fetch_university_row(
    database: SCDBMySQL,
    *,
    university_id: int | None = None,
    code: str | None = None,
) -> StoredUniversity:
    """按主键或代码读取一条高校记录。

    Args:
        database: 数据库客户端。
        university_id: 高校主键。
        code: 高校代码。

    Returns:
        StoredUniversity: 查询到的高校记录。

    Raises:
        LookupError: 未找到记录时抛出。
    """
    if university_id is not None:
        row = database.fetchone(
            """
            SELECT id, name, code,
                   school_type AS type,
                   school_nature AS nature,
                   created_at AS saved_at
            FROM university
            WHERE id = %s
            """,
            (university_id,),
        )
    else:
        row = database.fetchone(
            """
            SELECT id, name, code,
                   school_type AS type,
                   school_nature AS nature,
                   created_at AS saved_at
            FROM university
            WHERE code = %s
            """,
            (code,),
        )
    if row is None:
        raise LookupError("未找到对应高校记录")

    return StoredUniversity(
        id=int(row["id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        type=str(row["type"]),
        nature=str(row["nature"]),
        saved_at=str(row["saved_at"]),
    )


def _fetch_major_group_row(database: SCDBMySQL, major_group_id: int) -> StoredMajorGroup:
    """按主键读取一条专业组记录。

    Args:
        database: 数据库客户端。
        major_group_id: 专业组主键。

    Returns:
        StoredMajorGroup: 查询到的专业组记录。

    Raises:
        LookupError: 未找到记录时抛出。
    """
    row = database.fetchone(
        """
        SELECT mg.id, mg.university_id, mg.name, mg.code,
               u.name AS university_name,
               u.code AS university_code,
               mg.created_at AS saved_at
        FROM major_group AS mg
        INNER JOIN university AS u ON u.id = mg.university_id
        WHERE mg.id = %s
        """,
        (major_group_id,),
    )
    if row is None:
        raise LookupError("未找到对应专业组记录")

    return StoredMajorGroup(
        id=int(row["id"]),
        university_id=int(row["university_id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        university_name=str(row["university_name"]),
        university_code=str(row["university_code"]),
        saved_at=str(row["saved_at"]),
    )


def get_university_catalog_summary() -> UniversityCatalogSummary:
    """返回高校与专业组总量统计。

    Returns:
        UniversityCatalogSummary: 当前高校与专业组总数。
    """
    database = _university_database()
    row = database.fetchone(
        """
        SELECT
            (SELECT COUNT(*) FROM university) AS total_universities,
            (SELECT COUNT(*) FROM major_group) AS total_major_groups
        """
    )
    return UniversityCatalogSummary(
        total_universities=int(row["total_universities"]),
        total_major_groups=int(row["total_major_groups"]),
    )


def find_university_by_name(name: str) -> StoredUniversity | None:
    """按高校名称查询现有记录。

    Args:
        name: 高校名称。

    Returns:
        StoredUniversity | None: 命中时返回高校记录，否则返回 None。
    """
    clean_name = name.strip()
    if not clean_name:
        return None

    database = _university_database()
    row = database.fetchone(
        """
        SELECT id, name, code,
               school_type AS type,
               school_nature AS nature,
               created_at AS saved_at
        FROM university
        WHERE name = %s
        """,
        (clean_name,),
    )
    if row is None:
        return None

    return StoredUniversity(
        id=int(row["id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        type=str(row["type"]),
        nature=str(row["nature"]),
        saved_at=str(row["saved_at"]),
    )


def find_university_by_code(code: str) -> StoredUniversity | None:
    """按高校代码查询现有记录。

    Args:
        code: 高校代码。

    Returns:
        StoredUniversity | None: 命中时返回高校记录，否则返回 None。
    """
    clean_code = code.strip()
    if not clean_code:
        return None

    database = _university_database()
    row = database.fetchone(
        """
        SELECT id, name, code,
               school_type AS type,
               school_nature AS nature,
               created_at AS saved_at
        FROM university
        WHERE code = %s
        """,
        (clean_code,),
    )
    if row is None:
        return None

    return StoredUniversity(
        id=int(row["id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        type=str(row["type"]),
        nature=str(row["nature"]),
        saved_at=str(row["saved_at"]),
    )


def find_major_group_by_name(
    university_id: int,
    name: str,
) -> StoredMajorGroup | None:
    """按高校和专业组名称查询现有记录。

    Args:
        university_id: 所属高校主键。
        name: 专业组名称。

    Returns:
        StoredMajorGroup | None: 命中时返回专业组记录，否则返回 None。
    """
    clean_name = name.strip()
    if not clean_name:
        return None

    database = _university_database()
    row = database.fetchone(
        """
        SELECT mg.id, mg.university_id, mg.name, mg.code,
               u.name AS university_name,
               u.code AS university_code,
               mg.created_at AS saved_at
        FROM major_group AS mg
        INNER JOIN university AS u ON u.id = mg.university_id
        WHERE mg.university_id = %s AND mg.name = %s
        """,
        (university_id, clean_name),
    )
    if row is None:
        return None

    return StoredMajorGroup(
        id=int(row["id"]),
        university_id=int(row["university_id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        university_name=str(row["university_name"]),
        university_code=str(row["university_code"]),
        saved_at=str(row["saved_at"]),
    )


def find_major_group_by_code(
    university_id: int,
    code: str,
) -> StoredMajorGroup | None:
    """按高校和专业组代码查询现有记录。

    Args:
        university_id: 所属高校主键。
        code: 专业组代码。

    Returns:
        StoredMajorGroup | None: 命中时返回专业组记录，否则返回 None。
    """
    clean_code = code.strip()
    if not clean_code:
        return None

    database = _university_database()
    row = database.fetchone(
        """
        SELECT mg.id, mg.university_id, mg.name, mg.code,
               u.name AS university_name,
               u.code AS university_code,
               mg.created_at AS saved_at
        FROM major_group AS mg
        INNER JOIN university AS u ON u.id = mg.university_id
        WHERE mg.university_id = %s AND mg.code = %s
        """,
        (university_id, clean_code),
    )
    if row is None:
        return None

    return StoredMajorGroup(
        id=int(row["id"]),
        university_id=int(row["university_id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        university_name=str(row["university_name"]),
        university_code=str(row["university_code"]),
        saved_at=str(row["saved_at"]),
    )


def list_universities() -> list[StoredUniversity]:
    """返回全部已保存高校。

    Returns:
        list[StoredUniversity]: 按保存时间与主键升序排列的高校清单。
    """
    database = _university_database()
    rows = database.fetchall(
        """
        SELECT id, name, code,
               school_type AS type,
               school_nature AS nature,
               created_at AS saved_at
        FROM university
        ORDER BY created_at ASC, id ASC
        LIMIT 1000
        """
    )
    return [
        StoredUniversity(
            id=int(row["id"]),
            name=str(row["name"]),
            code=str(row["code"]),
            type=str(row["type"]),
            nature=str(row["nature"]),
            saved_at=str(row["saved_at"]),
        )
        for row in rows
    ]


def save_university(
    university_id: str,
    name: str,
    code: str,
    school_type: str,
    nature: str,
) -> tuple[StoredUniversity, bool]:
    """保存或覆盖修改一条高校记录。

    Args:
        university_id: 可选的高校主键；为空时新增。
        name: 高校名称。
        code: 高校代码。
        school_type: 高校办学类型。
        nature: 高校层次。

    Returns:
        tuple[StoredUniversity, bool]: 保存后的记录，以及是否为新增。

    Raises:
        ValueError: 字段校验失败或出现重复值时抛出。
    """
    current_id = _parse_record_id(university_id)
    payload = _normalize_university(name, code, school_type, nature)
    database = _university_database()

    if current_id is not None:
        existing = database.fetchone(
            "SELECT id FROM university WHERE id = %s",
            (current_id,),
        )
        if existing is None:
            raise ValueError("要修改的高校不存在，请刷新页面后重试")

    duplicate_name = database.fetchone(
        "SELECT id FROM university WHERE name = %s AND (%s IS NULL OR id <> %s)",
        (payload["name"], current_id, current_id),
    )
    if duplicate_name is not None:
        raise ValueError("高校名称不能重复保存")

    duplicate_code = database.fetchone(
        "SELECT id FROM university WHERE code = %s AND (%s IS NULL OR id <> %s)",
        (payload["code"], current_id, current_id),
    )
    if duplicate_code is not None:
        raise ValueError("高校代码不能重复保存")

    if current_id is None:
        database.insert(
            "university",
            {
                "name": payload["name"],
                "code": payload["code"],
                "school_type": payload["type"],
                "school_nature": payload["nature"],
            },
        )
        return _fetch_university_row(database, code=payload["code"]), True

    database.execute(
        """
        UPDATE university
        SET name = %s,
            code = %s,
            school_type = %s,
            school_nature = %s
        WHERE id = %s
        """,
        (
            payload["name"],
            payload["code"],
            payload["type"],
            payload["nature"],
            current_id,
        ),
        read_only=False,
    )
    return _fetch_university_row(database, university_id=current_id), False


def list_major_groups(university_id: int) -> list[StoredMajorGroup]:
    """返回某一高校下的全部专业组。

    Args:
        university_id: 所属高校主键。

    Returns:
        list[StoredMajorGroup]: 按保存时间与主键升序排列的专业组清单。

    Raises:
        ValueError: 高校不存在时抛出。
    """
    database = _university_database()
    university = database.fetchone(
        "SELECT id FROM university WHERE id = %s",
        (university_id,),
    )
    if university is None:
        raise ValueError("请选择有效的高校")

    rows = database.fetchall(
        """
        SELECT mg.id, mg.university_id, mg.name, mg.code,
               u.name AS university_name,
               u.code AS university_code,
               mg.created_at AS saved_at
        FROM major_group AS mg
        INNER JOIN university AS u ON u.id = mg.university_id
        WHERE mg.university_id = %s
        ORDER BY mg.created_at ASC, mg.id ASC
        LIMIT 1000
        """,
        (university_id,),
    )
    return [
        StoredMajorGroup(
            id=int(row["id"]),
            university_id=int(row["university_id"]),
            name=str(row["name"]),
            code=str(row["code"]),
            university_name=str(row["university_name"]),
            university_code=str(row["university_code"]),
            saved_at=str(row["saved_at"]),
        )
        for row in rows
    ]


def save_major_group(
    major_group_id: str,
    university_id: str,
    name: str,
    code: str,
) -> tuple[StoredMajorGroup, bool]:
    """保存或覆盖修改一条专业组记录。

    Args:
        major_group_id: 可选的专业组主键；为空时新增。
        university_id: 所属高校主键。
        name: 专业组名称。
        code: 专业组代码。

    Returns:
        tuple[StoredMajorGroup, bool]: 保存后的记录，以及是否为新增。

    Raises:
        ValueError: 字段校验失败、所属高校不存在或出现重复值时抛出。
    """
    current_id = _parse_record_id(major_group_id)
    payload = _normalize_major_group(university_id, name, code)
    database = _university_database()

    university = database.fetchone(
        "SELECT id FROM university WHERE id = %s",
        (payload["university_id"],),
    )
    if university is None:
        raise ValueError("请选择有效的高校")

    if current_id is not None:
        existing = database.fetchone(
            "SELECT id FROM major_group WHERE id = %s",
            (current_id,),
        )
        if existing is None:
            raise ValueError("要修改的专业组不存在，请刷新页面后重试")

    duplicate_name = database.fetchone(
        """
        SELECT id
        FROM major_group
        WHERE university_id = %s AND name = %s AND (%s IS NULL OR id <> %s)
        """,
        (payload["university_id"], payload["name"], current_id, current_id),
    )
    if duplicate_name is not None:
        raise ValueError("同一高校内专业组名称不能重复保存")

    duplicate_code = database.fetchone(
        """
        SELECT id
        FROM major_group
        WHERE university_id = %s AND code = %s AND (%s IS NULL OR id <> %s)
        """,
        (payload["university_id"], payload["code"], current_id, current_id),
    )
    if duplicate_code is not None:
        raise ValueError("同一高校内专业组代码不能重复保存")

    if current_id is None:
        database.insert(
            "major_group",
            {
                "university_id": payload["university_id"],
                "name": payload["name"],
                "code": payload["code"],
            },
        )
        row = database.fetchone(
            """
            SELECT mg.id
            FROM major_group AS mg
            WHERE mg.university_id = %s AND mg.code = %s
            """,
            (payload["university_id"], payload["code"]),
        )
        if row is None:
            raise LookupError("未找到刚保存的专业组记录")
        return _fetch_major_group_row(database, int(row["id"])), True

    database.execute(
        """
        UPDATE major_group
        SET university_id = %s,
            name = %s,
            code = %s
        WHERE id = %s
        """,
        (
            payload["university_id"],
            payload["name"],
            payload["code"],
            current_id,
        ),
        read_only=False,
    )
    return _fetch_major_group_row(database, current_id), False