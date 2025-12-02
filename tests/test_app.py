import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from api import app as app_module


class FakeDBState:
    def __init__(self):
        self.todos = []
        self.next_id = 1


class FakeCursor:
    def __init__(self, state: FakeDBState):
        self.state = state
        self.results = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.strip().replace("\n", " ").split())
        upper = normalized.upper()
        self.results = []
        self.rowcount = 0

        if upper.startswith("SELECT 1"):
            self.results = [(1,)]
        elif "CREATE TABLE" in upper:
            return
        elif upper.startswith("SELECT ID, TITLE, COMPLETED FROM TODOS ORDER BY ID"):
            self.results = [todo.copy() for todo in self.state.todos]
        elif upper.startswith("SELECT ID, TITLE, COMPLETED FROM TODOS WHERE ID ="):
            todo_id = params[0]
            todo = next((t for t in self.state.todos if t["id"] == todo_id), None)
            if todo:
                self.results = [todo.copy()]
        elif upper.startswith("INSERT INTO TODOS"):
            title, completed = params
            todo = {"id": self.state.next_id, "title": title, "completed": completed}
            self.state.next_id += 1
            self.state.todos.append(todo)
            self.results = [todo.copy()]
            self.rowcount = 1
        elif upper.startswith("UPDATE TODOS SET TITLE ="):
            title, completed, todo_id = params
            todo = next((t for t in self.state.todos if t["id"] == todo_id), None)
            if todo:
                todo.update({"title": title, "completed": completed})
                self.results = [todo.copy()]
                self.rowcount = 1
        elif upper.startswith("DELETE FROM TODOS WHERE ID ="):
            todo_id = params[0]
            before = len(self.state.todos)
            self.state.todos = [t for t in self.state.todos if t["id"] != todo_id]
            self.rowcount = 1 if len(self.state.todos) < before else 0

    def fetchone(self):
        if not self.results:
            return None
        return self.results.pop(0)

    def fetchall(self):
        return self.results


class FakeConnection:
    def __init__(self, state: FakeDBState):
        self.state = state

    def cursor(self, cursor_factory=None):
        return FakeCursor(self.state)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def close(self):
        return


class TodoApiTestCase(unittest.TestCase):
    def setUp(self):
        self.state = FakeDBState()
        self.original_get_db = app_module.get_db_connection
        self.fake_connection_factory = lambda: FakeConnection(self.state)
        app_module.get_db_connection = self.fake_connection_factory
        app_module.init_db()
        self.client_context = TestClient(app_module.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        app_module.get_db_connection = self.original_get_db

    def test_ping(self):
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["db"])

    def test_create_and_list_todos(self):
        create_resp = self.client.post("/todos", json={"title": "Comprar pan"})
        self.assertEqual(create_resp.status_code, 201)
        created = create_resp.json()
        self.assertEqual(created["title"], "Comprar pan")
        self.assertFalse(created["completed"])

        list_resp = self.client.get("/todos")
        self.assertEqual(list_resp.status_code, 200)
        todos = list_resp.json()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Comprar pan")

    def test_update_todo(self):
        create_resp = self.client.post("/todos", json={"title": "Aprender FastAPI"})
        todo_id = create_resp.json()["id"]

        update_resp = self.client.put(f"/todos/{todo_id}", json={"completed": True})
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.json()
        self.assertEqual(updated["id"], todo_id)
        self.assertTrue(updated["completed"])
        self.assertEqual(updated["title"], "Aprender FastAPI")

    def test_delete_todo(self):
        create_resp = self.client.post("/todos", json={"title": "Borrar tarea"})
        todo_id = create_resp.json()["id"]

        delete_resp = self.client.delete(f"/todos/{todo_id}")
        self.assertEqual(delete_resp.status_code, 204)

        missing_resp = self.client.delete(f"/todos/{todo_id}")
        self.assertEqual(missing_resp.status_code, 404)

        list_resp = self.client.get("/todos")
        self.assertEqual(list_resp.json(), [])

    def test_update_requires_payload(self):
        create_resp = self.client.post("/todos", json={"title": "algo"})
        todo_id = create_resp.json()["id"]

        response = self.client.put(f"/todos/{todo_id}", json={})
        self.assertEqual(response.status_code, 400)

    def test_update_missing_todo_returns_404(self):
        response = self.client.put("/todos/999", json={"title": "n/a"})
        self.assertEqual(response.status_code, 404)

    def test_db_check_failure_path(self):
        original_factory = app_module.get_db_connection

        def raising_connection():
            raise RuntimeError("db down")

        app_module.get_db_connection = raising_connection
        try:
            self.assertFalse(app_module.db_check())
        finally:
            app_module.get_db_connection = original_factory

    def test_get_db_connection_uses_psycopg2(self):
        with mock.patch("api.app.psycopg2.connect") as mock_connect:
            with mock.patch.dict(
                os.environ,
                {
                    "DB_HOST": "localhost",
                    "DB_PORT": "1234",
                    "POSTGRES_USER": "user1",
                    "POSTGRES_PASSWORD": "pass1",
                    "POSTGRES_DB": "db1",
                },
                clear=False,
            ):
                conn = self.original_get_db()
                mock_connect.assert_called_once_with(
                    host="localhost",
                    port="1234",
                    user="user1",
                    password="pass1",
                    dbname="db1",
                    connect_timeout=2,
                )
                self.assertEqual(conn, mock_connect.return_value)
