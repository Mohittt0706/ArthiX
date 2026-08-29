import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from database.db import init_db, reset_db, get_session, Base, close_session


def _make_test_app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["DEMO_MODE"] = "true"

    import importlib
    import config as config_mod
    importlib.reload(config_mod)

    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    return app


class TestAuth(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.app = _make_test_app()
        self.client = self.app.test_client()

    def tearDown(self):
        reset_db()

    def test_register_success(self):
        res = self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["user"]["username"], "testuser")

    def test_register_duplicate(self):
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        res = self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test2@example.com",
            "password": "password123"
        })
        self.assertEqual(res.status_code, 409)

    def test_register_missing_fields(self):
        res = self.client.post("/api/auth/register", json={
            "username": "test"
        })
        self.assertEqual(res.status_code, 400)

    def test_login_success(self):
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        res = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        self.assertEqual(res.status_code, 200)

    def test_login_wrong_password(self):
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        res = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        self.assertEqual(res.status_code, 401)

    def test_me_authenticated(self):
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["authenticated"])

    def test_me_unauthenticated(self):
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_logout(self):
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        res = self.client.post("/api/auth/logout")
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)


class TestAnalysisAPI(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.app = _make_test_app()
        self.client = self.app.test_client()
        self.client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })

    def tearDown(self):
        reset_db()

    def test_search(self):
        res = self.client.get("/api/search?q=TCS")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreater(len(data), 0)

    def test_search_empty(self):
        res = self.client.get("/api/search?q=")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])

    def test_analyze_requires_auth(self):
        self.client.post("/api/auth/logout")
        res = self.client.post("/api/analyze", json={"symbol": "TCS"})
        self.assertEqual(res.status_code, 401)

    def test_analyze_stock(self):
        res = self.client.post("/api/analyze", json={"symbol": "TCS"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("verdict", data)
        self.assertIn("evidence", data)
        self.assertIn("agent_outputs", data)
        self.assertIn(data["verdict"]["verdict"], ["BUY", "WATCH", "AVOID"])

    def test_watchlist_add_remove(self):
        res = self.client.post("/api/watchlist", json={"symbol": "TCS", "name": "TCS"})
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/watchlist")
        self.assertEqual(len(res.get_json()), 1)
        res = self.client.delete("/api/watchlist/TCS")
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/watchlist")
        self.assertEqual(len(res.get_json()), 0)


class TestHealth(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.app = _make_test_app()
        self.client = self.app.test_client()

    def tearDown(self):
        reset_db()

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app"], "ArthiX")


if __name__ == "__main__":
    unittest.main()
