"""学生 MySQL 持久化的最小回归检查。"""

import datetime
import os
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from alt_web01 import create_app
from alt_web01.services import add_student, list_students


class StudentPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.connection.cursor.return_value.__enter__.return_value = self.cursor

    @patch("alt_web01._configure_logging")
    def test_create_app_reads_secret_key(
        self, _configure_logging: MagicMock
    ) -> None:
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret"}):
            app = create_app()

        self.assertEqual(app.secret_key, "test-secret")

    @patch("alt_web01.services.pymysql.connect")
    def test_add_student_uses_parameterized_insert(self, connect: MagicMock) -> None:
        connect.return_value = self.connection

        student = add_student(" 张三 ", "男", "2004-01-02")

        self.assertEqual(
            student, {"name": "张三", "gender": "男", "birthday": "2004-01-02"}
        )
        self.cursor.execute.assert_any_call(
            "INSERT INTO students (name, gender, birthday) VALUES (%s, %s, %s)",
            ("张三", "男", "2004-01-02"),
        )
        self.connection.commit.assert_called_once_with()

    @patch("alt_web01.services.pymysql.connect")
    def test_list_students_reads_database_rows(self, connect: MagicMock) -> None:
        connect.return_value = self.connection
        self.cursor.fetchall.return_value = [
            {
                "id": 7,
                "name": "李四",
                "gender": "女",
                "birthday": datetime.date(2003, 5, 6),
                "age": Decimal("23.3"),
                "saved_at": datetime.datetime(2026, 8, 24, 9, 30),
            }
        ]

        self.assertEqual(
            list_students(),
            [
                {
                    "id": 7,
                    "name": "李四",
                    "gender": "女",
                    "birthday": "2003-05-06",
                    "age": 23.3,
                    "saved_at": "2026-08-24 09:30:00",
                }
            ],
        )
        query = self.cursor.execute.call_args_list[-1].args[0]
        self.assertIn("DATEDIFF(CURDATE(), birthday) / 365.2425", query)
        self.assertIn("ORDER BY created_at DESC, id DESC", query)
        self.assertIn("LIMIT 1000", query)

    @patch("alt_web01.blueprints.students.list_students")
    @patch("alt_web01._configure_logging")
    def test_page_initializes_datatables(
        self, _configure_logging: MagicMock, list_saved: MagicMock
    ) -> None:
        list_saved.return_value = [
            {
                "id": 9,
                "name": "赵六",
                "gender": "女",
                "birthday": "2001-02-03",
                "age": 25.6,
                "saved_at": "2026-08-24 10:20:30",
            }
        ]
        app = create_app()

        response = app.test_client().get("/students/add-manual")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("new DataTable('#student-table'", page)
        self.assertIn("order: [[5, 'desc'], [0, 'desc']]", page)
        self.assertIn("25.6", page)
        self.assertIn("2026-08-24 10:20:30", page)

    @patch("alt_web01.blueprints.students.add_student")
    @patch("alt_web01._configure_logging")
    def test_form_post_saves_student(
        self, _configure_logging: MagicMock, add: MagicMock
    ) -> None:
        add.return_value = {"name": "王五", "gender": "男", "birthday": "2002-03-04"}
        app = create_app()

        response = app.test_client().post(
            "/students/add-manual",
            data={"name": "王五", "gender": "男", "birthday": "2002-03-04"},
        )

        self.assertEqual(response.status_code, 302)
        add.assert_called_once_with("王五", "男", "2002-03-04")


if __name__ == "__main__":
    unittest.main()
