"""高校与专业组的最小回归检查。"""

import unittest
from unittest.mock import MagicMock, patch

from alt_web01 import create_app
from alt_web01.ai_services import (
    apply_university_plan,
    build_auto_page_context,
    generate_university_plan,
)
from alt_web01 import university_services
from alt_web01.university_services import (
    get_university_catalog_summary,
    list_major_groups,
    list_recent_major_groups,
    list_universities,
    save_major_group,
    save_university,
)


class UniversityServiceTest(unittest.TestCase):
    @patch("alt_web01.university_services._prepared_database")
    def test_save_university_inserts_new_row(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.side_effect = [None, None, {
            "id": 3,
            "name": "东海工学院",
            "code": "101",
            "type": "公办",
            "nature": "一本",
            "saved_at": "2026-08-26 22:20:00",
        }]

        university, created = save_university("", "东海工学院", "101", "公办", "一本")

        self.assertTrue(created)
        self.assertEqual(university["id"], 3)
        database.insert.assert_called_once_with(
            "university",
            {
                "name": "东海工学院",
                "code": "101",
                "school_type": "公办",
                "school_nature": "一本",
            },
        )

    @patch("alt_web01.university_services._prepared_database")
    def test_save_university_rejects_duplicate_code(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.side_effect = [None, {"id": 8}]

        with self.assertRaisesRegex(ValueError, "高校代码不能重复保存"):
            save_university("", "东海工学院", "101", "公办", "一本")

    @patch("alt_web01.university_services._prepared_database")
    def test_save_university_updates_existing_row(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.side_effect = [
            {"id": 6},
            None,
            None,
            {
                "id": 6,
                "name": "北原大学",
                "code": "205",
                "type": "民办",
                "nature": "其他",
                "saved_at": "2026-08-26 22:21:00",
            },
        ]

        university, created = save_university("6", "北原大学", "205", "民办", "其他")

        self.assertFalse(created)
        self.assertEqual(university["name"], "北原大学")
        update_sql = database.execute.call_args.args[0]
        self.assertIn("UPDATE university", update_sql)

    @patch("alt_web01.university_services._prepared_database")
    def test_list_universities_queries_in_ascending_order(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchall.return_value = [
            {
                "id": 1,
                "name": "东海工学院",
                "code": "101",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-26 22:22:00",
            }
        ]

        universities = list_universities()

        self.assertEqual(universities[0]["id"], 1)
        query = database.fetchall.call_args.args[0]
        self.assertIn("ORDER BY created_at ASC, id ASC", query)

    @patch("alt_web01.university_services._prepared_database")
    def test_save_major_group_inserts_new_row(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.side_effect = [
            {"id": 3},
            None,
            None,
            {"id": 9},
            {
                "id": 9,
                "university_id": 3,
                "name": "人工智能专业组",
                "code": "120301",
                "university_name": "东海工学院",
                "university_code": "101",
                "saved_at": "2026-08-26 22:23:00",
            },
        ]

        major_group, created = save_major_group("", "3", "人工智能专业组", "120301")

        self.assertTrue(created)
        self.assertEqual(major_group["university_id"], 3)
        database.insert.assert_called_once_with(
            "major_group",
            {
                "university_id": 3,
                "name": "人工智能专业组",
                "code": "120301",
            },
        )

    @patch("alt_web01.university_services._prepared_database")
    def test_save_major_group_rejects_duplicate_name_within_university(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.side_effect = [{"id": 3}, {"id": 10}]

        with self.assertRaisesRegex(ValueError, "同一高校内专业组名称不能重复保存"):
            save_major_group("", "3", "人工智能专业组", "120301")

    @patch("alt_web01.university_services._prepared_database")
    def test_list_major_groups_filters_by_university(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.return_value = {"id": 3}
        database.fetchall.return_value = [
            {
                "id": 9,
                "university_id": 3,
                "name": "人工智能专业组",
                "code": "120301",
                "university_name": "东海工学院",
                "university_code": "101",
                "saved_at": "2026-08-26 22:23:00",
            }
        ]

        major_groups = list_major_groups(3)

        self.assertEqual(major_groups[0]["name"], "人工智能专业组")
        query = database.fetchall.call_args.args[0]
        self.assertIn("WHERE mg.university_id = %s", query)
        self.assertIn("ORDER BY mg.created_at ASC, mg.id ASC", query)

    @patch("alt_web01.university_services._prepared_database")
    def test_list_recent_major_groups_queries_all_universities(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchall.return_value = [
            {
                "id": 4,
                "university_id": 2,
                "name": "智能制造专业组",
                "code": "080213",
                "university_name": "江南理工大学",
                "university_code": "118",
                "saved_at": "2026-08-27 10:00:00",
            }
        ]

        major_groups = list_recent_major_groups()

        self.assertEqual(major_groups[0]["university_name"], "江南理工大学")
        query = database.fetchall.call_args.args[0]
        self.assertIn("FROM major_group AS mg", query)
        self.assertNotIn("WHERE mg.university_id = %s", query)

    @patch("alt_web01.university_services._prepared_database")
    def test_get_university_catalog_summary_returns_counts(
        self, prepared_database: MagicMock
    ) -> None:
        database = prepared_database.return_value
        database.fetchone.return_value = {
            "total_universities": 2,
            "total_major_groups": 5,
        }

        summary = get_university_catalog_summary()

        self.assertEqual(summary["total_universities"], 2)
        self.assertEqual(summary["total_major_groups"], 5)


class UniversityAIServiceTest(unittest.TestCase):
    @patch("alt_web01.ai_services.list_recent_major_groups")
    @patch("alt_web01.ai_services.list_available_models")
    @patch("alt_web01.ai_services.list_universities")
    @patch("alt_web01.ai_services.get_university_catalog_summary")
    def test_build_auto_page_context_uses_latest_university(
        self,
        summary_mock: MagicMock,
        list_universities_mock: MagicMock,
        list_available_models_mock: MagicMock,
        list_recent_major_groups_mock: MagicMock,
    ) -> None:
        summary_mock.return_value = {
            "total_universities": 2,
            "total_major_groups": 3,
        }
        list_available_models_mock.return_value = [
            "deepseek-ai/DeepSeek-V4-Flash",
            "zai-org/GLM-5.2",
        ]
        list_universities_mock.return_value = [
            {
                "id": 1,
                "name": "东海工学院",
                "code": "101",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-27 09:00:00",
            },
            {
                "id": 2,
                "name": "江南理工大学",
                "code": "118",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-27 09:05:00",
            },
        ]
        list_recent_major_groups_mock.return_value = [
            {
                "id": 11,
                "university_id": 2,
                "name": "人工智能专业组",
                "code": "120301",
                "university_name": "江南理工大学",
                "university_code": "118",
                "saved_at": "2026-08-27 09:10:00",
            }
        ]

        context = build_auto_page_context(selected_model="zai-org/GLM-5.2")

        self.assertEqual(context["selected_university"]["id"], 2)
        self.assertEqual(context["recent_major_groups"][0]["name"], "人工智能专业组")
        self.assertEqual(context["ai_model"], "zai-org/GLM-5.2")

    @patch("alt_web01.ai_services.get_university_catalog_summary")
    @patch("alt_web01.ai_services._create_ai_client")
    def test_generate_university_plan_uses_selected_model(
        self,
        client_factory: MagicMock,
        summary_mock: MagicMock,
    ) -> None:
        summary_mock.return_value = {
            "total_universities": 1,
            "total_major_groups": 1,
        }
        client = client_factory.return_value
        client.chat.completions.create.return_value.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"universities": [{"name": "江南理工大学", "code": "118", "type": "公办", "nature": "一本", "major_groups": []}]}'
                )
            )
        ]

        plan = generate_university_plan("新增江南理工大学", model="zai-org/GLM-5.2")

        self.assertEqual(plan["universities"][0]["name"], "江南理工大学")
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["model"],
            "zai-org/GLM-5.2",
        )

    @patch("alt_web01.ai_services.get_university_catalog_summary")
    @patch("alt_web01.ai_services._create_ai_client")
    def test_generate_university_plan_backfills_missing_fields_from_prompt(
        self,
        client_factory: MagicMock,
        summary_mock: MagicMock,
    ) -> None:
        summary_mock.return_value = {
            "total_universities": 1,
            "total_major_groups": 1,
        }
        client = client_factory.return_value
        client.chat.completions.create.return_value.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"universities": [{"name": "", "code": "", "type": "", "nature": "其他", "major_groups": [{"name": "", "code": "080204"}]}]}'
                )
            )
        ]

        plan = generate_university_plan(
            "今天学校这块顺手处理一下，给南京工业大学补一个机械电子专业组080204，别的事情先不管。",
            model="zai-org/GLM-5.2",
        )

        self.assertEqual(plan["universities"][0]["name"], "南京工业大学")
        self.assertEqual(
            plan["universities"][0]["major_groups"][0]["name"],
            "机械电子专业组",
        )

    @patch("alt_web01.ai_services.save_major_group")
    @patch("alt_web01.ai_services.save_university")
    @patch("alt_web01.ai_services.find_major_group_by_name")
    @patch("alt_web01.ai_services.find_major_group_by_code")
    @patch("alt_web01.ai_services.find_university_by_name")
    @patch("alt_web01.ai_services.find_university_by_code")
    def test_apply_university_plan_saves_generated_records(
        self,
        find_by_code: MagicMock,
        find_by_name: MagicMock,
        find_major_by_code: MagicMock,
        find_major_by_name: MagicMock,
        save_university_mock: MagicMock,
        save_major_group_mock: MagicMock,
    ) -> None:
        find_by_code.return_value = None
        find_by_name.return_value = None
        find_major_by_code.return_value = None
        find_major_by_name.return_value = None
        save_university_mock.return_value = (
            {
                "id": 3,
                "name": "江南理工大学",
                "code": "118",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-27 09:00:00",
            },
            True,
        )
        save_major_group_mock.side_effect = [
            (
                {
                    "id": 11,
                    "university_id": 3,
                    "name": "人工智能专业组",
                    "code": "120301",
                    "university_name": "江南理工大学",
                    "university_code": "118",
                    "saved_at": "2026-08-27 09:01:00",
                },
                True,
            ),
            (
                {
                    "id": 12,
                    "university_id": 3,
                    "name": "智能制造专业组",
                    "code": "080213",
                    "university_name": "江南理工大学",
                    "university_code": "118",
                    "saved_at": "2026-08-27 09:02:00",
                },
                False,
            ),
        ]

        summary = apply_university_plan(
            {
                "universities": [
                    {
                        "name": "江南理工大学",
                        "code": "118",
                        "type": "公办",
                        "nature": "一本",
                        "major_groups": [
                            {"name": "人工智能专业组", "code": "120301"},
                            {"name": "智能制造专业组", "code": "080213"},
                        ],
                    }
                ]
            }
        )

        self.assertEqual(summary["universities_created"], 1)
        self.assertEqual(summary["universities_updated"], 0)
        self.assertEqual(summary["major_groups_created"], 1)
        self.assertEqual(summary["major_groups_updated"], 1)
        save_university_mock.assert_called_once()
        self.assertEqual(save_major_group_mock.call_count, 2)

    @patch("alt_web01.ai_services.save_major_group")
    @patch("alt_web01.ai_services.save_university")
    @patch("alt_web01.ai_services.find_major_group_by_name")
    @patch("alt_web01.ai_services.find_major_group_by_code")
    @patch("alt_web01.ai_services.find_university_by_name")
    @patch("alt_web01.ai_services.find_university_by_code")
    def test_apply_university_plan_uses_existing_university_when_ai_returns_partial_fields(
        self,
        find_by_code: MagicMock,
        find_by_name: MagicMock,
        find_major_by_code: MagicMock,
        find_major_by_name: MagicMock,
        save_university_mock: MagicMock,
        save_major_group_mock: MagicMock,
    ) -> None:
        find_by_code.return_value = None
        find_by_name.return_value = {
            "id": 1,
            "name": "南京工业大学",
            "code": "102",
            "type": "公办",
            "nature": "985",
            "saved_at": "2026-08-27 09:00:00",
        }
        find_major_by_code.return_value = None
        find_major_by_name.return_value = None
        save_university_mock.return_value = (
            {
                "id": 1,
                "name": "南京工业大学",
                "code": "102",
                "type": "公办",
                "nature": "985",
                "saved_at": "2026-08-27 09:00:00",
            },
            False,
        )
        save_major_group_mock.return_value = (
            {
                "id": 19,
                "university_id": 1,
                "name": "机械电子专业组",
                "code": "080204",
                "university_name": "南京工业大学",
                "university_code": "102",
                "saved_at": "2026-08-27 09:10:00",
            },
            True,
        )

        summary = apply_university_plan(
            {
                "universities": [
                    {
                        "name": "南京工业大学",
                        "code": "",
                        "type": "",
                        "nature": "",
                        "major_groups": [
                            {"name": "机械电子专业组", "code": "080204"}
                        ],
                    }
                ]
            }
        )

        self.assertEqual(summary["universities_updated"], 1)
        self.assertEqual(summary["major_groups_created"], 1)
        save_university_mock.assert_called_once_with(
            "1",
            "南京工业大学",
            "102",
            "公办",
            "985",
        )

    @patch("alt_web01.ai_services.save_major_group")
    @patch("alt_web01.ai_services.save_university")
    @patch("alt_web01.ai_services.find_major_group_by_name")
    @patch("alt_web01.ai_services.find_major_group_by_code")
    @patch("alt_web01.ai_services.find_university_by_name")
    @patch("alt_web01.ai_services.find_university_by_code")
    def test_apply_university_plan_keeps_existing_nature_when_ai_returns_other(
        self,
        find_by_code: MagicMock,
        find_by_name: MagicMock,
        find_major_by_code: MagicMock,
        find_major_by_name: MagicMock,
        save_university_mock: MagicMock,
        save_major_group_mock: MagicMock,
    ) -> None:
        find_by_code.return_value = None
        find_by_name.return_value = {
            "id": 1,
            "name": "南京工业大学",
            "code": "102",
            "type": "公办",
            "nature": "985",
            "saved_at": "2026-08-27 09:00:00",
        }
        find_major_by_code.return_value = None
        find_major_by_name.return_value = None
        save_university_mock.return_value = (
            {
                "id": 1,
                "name": "南京工业大学",
                "code": "102",
                "type": "公办",
                "nature": "985",
                "saved_at": "2026-08-27 09:00:00",
            },
            False,
        )
        save_major_group_mock.return_value = (
            {
                "id": 19,
                "university_id": 1,
                "name": "机械电子专业组",
                "code": "080204",
                "university_name": "南京工业大学",
                "university_code": "102",
                "saved_at": "2026-08-27 09:10:00",
            },
            True,
        )

        apply_university_plan(
            {
                "universities": [
                    {
                        "name": "南京工业大学",
                        "code": "",
                        "type": "",
                        "nature": "其他",
                        "major_groups": [
                            {"name": "机械电子专业组", "code": "080204"}
                        ],
                    }
                ]
            }
        )

        save_university_mock.assert_called_once_with(
            "1",
            "南京工业大学",
            "102",
            "公办",
            "985",
        )


class UniversityBlueprintTest(unittest.TestCase):
    @patch("alt_web01.blueprints.universities.list_universities")
    @patch("alt_web01._configure_logging")
    def test_university_page_renders_datatable(
        self, _configure_logging: MagicMock, list_saved: MagicMock
    ) -> None:
        list_saved.return_value = [
            {
                "id": 1,
                "name": "东海工学院",
                "code": "101",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-26 22:24:00",
            }
        ]
        app = create_app()

        response = app.test_client().get("/universities/add-manual")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("new DataTable('#university-table'", page)
        self.assertIn("东海工学院", page)
        self.assertIn("覆盖保存高校", page)

    @patch("alt_web01.blueprints.universities.list_major_groups")
    @patch("alt_web01.blueprints.universities.list_universities")
    @patch("alt_web01._configure_logging")
    def test_major_group_page_renders_selected_university_groups(
        self,
        _configure_logging: MagicMock,
        list_saved: MagicMock,
        list_groups: MagicMock,
    ) -> None:
        list_saved.return_value = [
            {
                "id": 3,
                "name": "东海工学院",
                "code": "101",
                "type": "公办",
                "nature": "一本",
                "saved_at": "2026-08-26 22:24:00",
            }
        ]
        list_groups.return_value = [
            {
                "id": 9,
                "university_id": 3,
                "name": "人工智能专业组",
                "code": "120301",
                "university_name": "东海工学院",
                "university_code": "101",
                "saved_at": "2026-08-26 22:25:00",
            }
        ]
        app = create_app()

        response = app.test_client().get("/universities/add-major-group?university_id=3")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("new DataTable('#major-group-table'", page)
        self.assertIn("人工智能专业组", page)
        self.assertIn('id="major-group-filter"', page)
        self.assertIn('data-major-group-id="9"', page)
        self.assertIn('<td class="col-index text-muted">1</td>', page)

    @patch("alt_web01.blueprints.universities.save_major_group")
    @patch("alt_web01._configure_logging")
    def test_major_group_post_redirects_to_selected_university(
        self, _configure_logging: MagicMock, save_group: MagicMock
    ) -> None:
        save_group.return_value = (
            {
                "id": 9,
                "university_id": 3,
                "name": "人工智能专业组",
                "code": "120301",
                "university_name": "东海工学院",
                "university_code": "101",
                "saved_at": "2026-08-26 22:25:00",
            },
            True,
        )
        app = create_app()

        response = app.test_client().post(
            "/universities/add-major-group",
            data={
                "major_group_id": "",
                "university_id": "3",
                "name": "人工智能专业组",
                "code": "120301",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/universities/add-major-group?university_id=3", response.location)

    @patch("alt_web01.blueprints.universities.build_auto_page_context")
    @patch("alt_web01._configure_logging")
    def test_auto_page_renders_prompt_panel(
        self, _configure_logging: MagicMock, context_builder: MagicMock
    ) -> None:
        context_builder.return_value = {
            "title": "自动添加大学和专业组",
            "summary": {"total_universities": 1, "total_major_groups": 2},
            "prompt_text": "",
            "generated_plan": None,
            "workflow_result": None,
            "universities": [],
            "recent_major_groups": [],
            "selected_university": None,
            "ai_model": "deepseek-ai/DeepSeek-V4-Flash",
            "model_options": ["deepseek-ai/DeepSeek-V4-Flash"],
        }
        app = create_app()

        response = app.test_client().get("/universities/add-auto")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("自然语言录入", page)
        self.assertIn('name="prompt"', page)
        self.assertIn('name="model"', page)
        self.assertIn('<select class="form-select form-select-lg" id="ai-model" name="model" required>', page)

    @patch("alt_web01.blueprints.universities.run_university_auto_workflow")
    @patch("alt_web01.blueprints.universities.build_auto_page_context")
    @patch("alt_web01._configure_logging")
    def test_auto_post_renders_workflow_result(
        self,
        _configure_logging: MagicMock,
        context_builder: MagicMock,
        workflow: MagicMock,
    ) -> None:
        context_builder.return_value = {
            "title": "自动添加大学和专业组",
            "summary": {"total_universities": 1, "total_major_groups": 2},
            "prompt_text": "",
            "generated_plan": None,
            "workflow_result": None,
            "universities": [],
            "recent_major_groups": [],
            "selected_university": None,
            "ai_model": "deepseek-ai/DeepSeek-V4-Flash",
            "model_options": ["deepseek-ai/DeepSeek-V4-Flash"],
        }
        workflow.return_value = {
            "model": "zai-org/GLM-5.2",
            "prompt": "新增江南理工大学",
            "summary": {"total_universities": 2, "total_major_groups": 3},
            "generated_plan": {
                "universities": [
                    {
                        "name": "江南理工大学",
                        "code": "118",
                        "type": "公办",
                        "nature": "一本",
                        "major_groups": [
                            {"name": "人工智能专业组", "code": "120301"}
                        ],
                    }
                ]
            },
            "save_summary": {
                "universities_created": 1,
                "universities_updated": 0,
                "major_groups_created": 1,
                "major_groups_updated": 0,
                "universities": [],
                "major_groups": [],
            },
            "result_universities": [
                {
                    "name": "江南理工大学",
                    "code": "118",
                    "type": "公办",
                    "nature": "一本",
                    "major_groups": [
                        {"name": "人工智能专业组", "code": "120301"}
                    ],
                }
            ],
        }
        app = create_app()

        response = app.test_client().post(
            "/universities/add-auto",
            data={"prompt": "新增江南理工大学", "model": "zai-org/GLM-5.2"},
        )
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("本次执行结果", page)
        self.assertIn("江南理工大学", page)
        workflow.assert_called_once_with("新增江南理工大学", "zai-org/GLM-5.2")


if __name__ == "__main__":
    unittest.main()