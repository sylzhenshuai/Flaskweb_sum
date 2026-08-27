"""学生 MySQL 持久化的最小回归检查。"""

import datetime
import os
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from alt_web01 import create_app
from alt_web01 import services
from alt_web01.services import add_student, list_students


class StudentPersistenceTest(unittest.TestCase):
    @patch("alt_web01._configure_logging")
    def test_create_app_reads_secret_key(
        self, _configure_logging: MagicMock
    ) -> None:
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret"}):
            app = create_app()

        self.assertEqual(app.secret_key, "test-secret")

    @patch("alt_web01.services._database")
    def test_add_student_uses_sedb_insert(self, database: MagicMock) -> None:
        db = database.return_value

        student = add_student(" 张三 ", "男", "2004-01-02")

        self.assertEqual(
            student, {"name": "张三", "gender": "男", "birthday": "2004-01-02"}
        )
        db.insert.assert_called_once_with(
            "students", {"name": "张三", "gender": "男", "birthday": "2004-01-02"}
        )
        create_sql = db.execute.call_args_list[0].args[0]
        self.assertIn("CREATE TABLE IF NOT EXISTS students", create_sql)

    @patch("alt_web01.services._discard_cached_database")
    @patch("alt_web01.services._database")
    def test_add_student_rebuilds_cached_client_after_connection_error(
        self, database: MagicMock, discard: MagicMock
    ) -> None:
        first_db = MagicMock()
        second_db = MagicMock()
        first_db.execute.side_effect = services.DatabaseConnectionError(
            "temporary connection failure"
        )
        database.side_effect = [first_db, second_db]

        student = add_student("张三", "男", "2004-01-02")

        self.assertEqual(
            student, {"name": "张三", "gender": "男", "birthday": "2004-01-02"}
        )
        discard.assert_called_once_with()
        second_db.insert.assert_called_once_with(
            "students", {"name": "张三", "gender": "男", "birthday": "2004-01-02"}
        )

    @patch("alt_web01.services._database")
    def test_list_students_reads_database_rows(self, database: MagicMock) -> None:
        db = database.return_value
        db.fetchall.return_value = [
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
        query = db.fetchall.call_args.args[0]
        self.assertIn("DATEDIFF(CURDATE(), birthday) / 365.2425", query)
        self.assertIn("ORDER BY created_at ASC, id ASC", query)
        self.assertIn("LIMIT 1000", query)

    @patch("alt_web01.services._discard_cached_database")
    @patch("alt_web01.services._database")
    def test_list_students_rebuilds_cached_client_after_connection_error(
        self, database: MagicMock, discard: MagicMock
    ) -> None:
        first_db = MagicMock()
        second_db = MagicMock()
        first_db.execute.side_effect = services.DatabaseConnectionError(
            "temporary connection failure"
        )
        second_db.fetchall.return_value = [
            {
                "id": 7,
                "name": "李四",
                "gender": "女",
                "birthday": datetime.date(2003, 5, 6),
                "age": Decimal("23.3"),
                "saved_at": datetime.datetime(2026, 8, 24, 9, 30),
            }
        ]
        database.side_effect = [first_db, second_db]

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
        discard.assert_called_once_with()

    @patch("alt_web01.services.SCDBMySQL")
    def test_database_uses_environment_and_bounded_pool(
        self, client: MagicMock
    ) -> None:
        services._database.cache_clear()
        try:
            with patch.dict(
                os.environ,
                {
                    "MYSQL_HOST": "db.example",
                    "MYSQL_PORT": "3307",
                    "MYSQL_DATABASE": "students_db",
                    "MYSQL_USER": "student_app",
                    "MYSQL_PASSWORD": "test-only",
                },
            ):
                database = services._database()

            self.assertIs(database, client.return_value)
            config, pool = client.call_args.args
            self.assertEqual(config.host, "db.example")
            self.assertEqual(config.port, 3307)
            self.assertEqual(config.database, "students_db")
            self.assertEqual(config.user, "student_app")
            self.assertEqual(pool.mincached, 0)
            self.assertEqual(pool.maxcached, 5)
            self.assertEqual(pool.maxconnections, 10)
        finally:
            services._database.cache_clear()

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
        self.assertIn("order: [[5, 'asc'], [0, 'asc']]", page)
        self.assertIn("25.6", page)
        self.assertIn("2026-08-24 10:20:30", page)

    @patch("alt_web01.blueprints.students.list_students")
    @patch("alt_web01._configure_logging")
    def test_page_stays_available_when_database_is_temporarily_unavailable(
        self, _configure_logging: MagicMock, list_saved: MagicMock
    ) -> None:
        list_saved.side_effect = RuntimeError("database unavailable")
        app = create_app()

        response = app.test_client().get("/students/add-manual")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("new DataTable('#student-table'", page)
        self.assertIn("数据库暂时不可用，已显示空清单", page)

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
