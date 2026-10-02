import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ingest as ingest_router
from app.schemas import IngestResult
from app.services.supabase_store import (
    AuthenticatedSupabase,
    get_site_record,
    list_site_records,
    require_authenticated_user,
    save_site_record,
)


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.ordering = None
        self.limit_value = None
        self.inserted_payload = None

    def select(self, _columns):
        return self

    def insert(self, payload):
        self.inserted_payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, desc=False, **_kwargs):
        self.ordering = (column, desc)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        if self.inserted_payload is not None:
            self.client.inserts.append((self.table_name, self.inserted_payload))
            return SimpleNamespace(data=[self.inserted_payload])

        self.client.queries.append(
            (self.table_name, list(self.filters), self.ordering, self.limit_value)
        )
        rows = list(self.client.rows.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        if self.ordering:
            column, desc = self.ordering
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.queries = []
        self.inserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class IngestRouteTests(unittest.TestCase):
    def setUp(self):
        self.authenticated = AuthenticatedSupabase(
            user_id="test-user",
            client=object(),
        )
        app.dependency_overrides[require_authenticated_user] = (
            lambda: self.authenticated
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_post_accepts_optional_title_and_source(self):
        result = IngestResult(
            category="daily_log",
            summary_english="North corridor completed.",
        )
        with (
            patch.object(ingest_router, "analyze_site_input", return_value=result),
            patch.object(ingest_router, "save_site_record") as save,
        ):
            response = self.client.post(
                "/ingest",
                data={
                    "project_id": "project-1",
                    "raw_text": "North corridor completed.",
                    "title": "  Corridor update ",
                    "source": "  Mobile app ",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["title"], "Corridor update")
        self.assertEqual(response.json()["source"], "Mobile app")
        save.assert_called_once_with(
            self.authenticated,
            "project-1",
            result,
            "North corridor completed.",
            None,
            "Corridor update",
            "Mobile app",
        )

    def test_list_route_requires_project_and_forwards_filters(self):
        records = [{"id": "snag-1", "category": "snag"}]
        with patch.object(ingest_router, "list_site_records", return_value=records) as listing:
            response = self.client.get(
                "/ingest",
                params={"project_id": "project-1", "category": "snag", "limit": 12},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), records)
        listing.assert_called_once_with(
            self.authenticated,
            "project-1",
            "snag",
            12,
        )

    def test_detail_route_returns_not_found_when_record_is_hidden_or_missing(self):
        with patch.object(ingest_router, "get_site_record", return_value=None) as lookup:
            response = self.client.get(
                "/ingest/unknown",
                params={"project_id": "project-1"},
            )

        self.assertEqual(response.status_code, 404)
        lookup.assert_called_once_with(
            self.authenticated,
            "project-1",
            "unknown",
            None,
        )


class SupabaseStoreTests(unittest.TestCase):
    def test_each_category_saves_to_its_table_with_metadata(self):
        expected_tables = {
            "daily_log": "daily_logs",
            "snag": "snags",
            "variation": "variations",
        }

        for category, expected_table in expected_tables.items():
            with self.subTest(category=category):
                client = FakeClient()
                authenticated = AuthenticatedSupabase(
                    user_id="test-user",
                    client=client,
                )
                result = IngestResult(
                    category=category,
                    summary_english="Client requested a scope change.",
                )

                save_site_record(
                    authenticated,
                    "project-1",
                    result,
                    "Original site note.",
                    None,
                    "Client request",
                    "Mobile app",
                )

                self.assertEqual(len(client.inserts), 1)
                table, payload = client.inserts[0]
                self.assertEqual(table, expected_table)
                self.assertEqual(payload["project_id"], "project-1")
                self.assertEqual(payload["title"], "Client request")
                self.assertEqual(payload["source"], "Mobile app")
                if category == "daily_log":
                    self.assertEqual(payload["user_id"], "test-user")

    def test_list_is_project_scoped_sorted_and_tagged(self):
        client = FakeClient(
            rows={
                "daily_logs": [
                    {
                        "id": "log-1",
                        "project_id": "project-1",
                        "created_at": "2026-10-02T12:00:00Z",
                    }
                ],
                "snags": [
                    {
                        "id": "snag-1",
                        "project_id": "project-1",
                        "created_at": "2026-10-02T13:00:00Z",
                    }
                ],
                "variations": [
                    {
                        "id": "variation-1",
                        "project_id": "another-project",
                        "created_at": "2026-10-02T14:00:00Z",
                    }
                ],
            }
        )
        authenticated = AuthenticatedSupabase(user_id="test-user", client=client)

        records = list_site_records(authenticated, "project-1", None, 10)

        self.assertEqual([record["category"] for record in records], ["snag", "daily_log"])
        self.assertTrue(
            all(
                ("project_id", "project-1") in filters
                for _table, filters, _ordering, _limit in client.queries
            )
        )
        self.assertTrue(all(ordering == ("created_at", True) for _, _, ordering, _ in client.queries))

    def test_detail_lookup_filters_by_project_and_record_id(self):
        client = FakeClient(
            rows={
                "snags": [
                    {
                        "id": "snag-1",
                        "project_id": "project-1",
                        "description": "Damaged finish",
                    },
                    {
                        "id": "snag-1",
                        "project_id": "another-project",
                        "description": "Other project record",
                    },
                ]
            }
        )
        authenticated = AuthenticatedSupabase(user_id="test-user", client=client)

        record = get_site_record(authenticated, "project-1", "snag-1", "snag")

        self.assertEqual(record["category"], "snag")
        self.assertEqual(record["description"], "Damaged finish")
        self.assertEqual(
            client.queries[0][1],
            [("project_id", "project-1"), ("id", "snag-1")],
        )


if __name__ == "__main__":
    unittest.main()