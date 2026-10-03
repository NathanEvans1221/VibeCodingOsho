import os
import sys
from urllib.parse import urlparse

import pytest
from flask import request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_SECRET = "test-secret-key-for-testing"
os.environ.setdefault("FLASK_SECRET_KEY", TEST_SECRET)
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("TRUSTED_PROXY_COUNT", "0")
os.environ.setdefault("ENABLE_HSTS", "false")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")


class TestApp:
    @pytest.fixture
    def app(self, monkeypatch):
        monkeypatch.setenv("FLASK_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("REDIS_URL", "")
        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "0")
        monkeypatch.setenv("ENABLE_HSTS", "false")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
        from app import create_app

        return create_app(
            {
                "TESTING": True,
                "SECRET_KEY": TEST_SECRET,
                "RATELIMIT_ENABLED": False,
            }
        )

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _csrf_token(self, client):
        response = client.get("/")
        assert response.status_code == 200
        marker = b'name="csrf_token" value="'
        token_start = response.data.index(marker) + len(marker)
        token_end = response.data.index(b'"', token_start)
        return response.data[token_start:token_end].decode()

    def test_index_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"csrf_token" in response.data

    def test_draw_rejects_get_requests(self, client):
        response = client.get("/draw")
        assert response.status_code == 405

    def test_draw_rejects_post_without_csrf_token(self, client):
        response = client.post("/draw")
        assert response.status_code == 400

    def test_draw_stores_result_and_history_in_session(self, client):
        token = self._csrf_token(client)
        response = client.post("/draw", data={"csrf_token": token})

        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/result"

        result = client.get("/result")
        assert result.status_code == 200
        card_names = ("愚者", "覺察", "轉化", "靜默", "勇氣")
        drawn_name = next(name for name in card_names if name.encode() in result.data)

        history = client.get("/history")
        assert history.status_code == 200
        assert drawn_name.encode() in history.data

    def test_result_without_draw_redirects_to_home(self, client):
        response = client.get("/result")
        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/"

    def test_history_page_renders_when_empty(self, client):
        response = client.get("/history")
        assert response.status_code == 200
        assert "目前尚無歷史記錄".encode() in response.data

    def test_404_error(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_hsts_header_is_disabled_by_default(self, client):
        response = client.get("/")
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_header_can_be_enabled(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_HSTS", "true")
        response = client.get("/")
        assert response.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )

    def test_trusted_proxy_count_configures_forwarded_address(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
        application = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": TEST_SECRET,
                "RATELIMIT_ENABLED": False,
            }
        )
        application.add_url_rule(
            "/remote-address",
            view_func=lambda: f"{request.remote_addr}|{request.is_secure}",
        )
        response = application.test_client().get(
            "/remote-address",
            headers={
                "X-Forwarded-For": "198.51.100.9",
                "X-Forwarded-Proto": "https",
            },
        )
        assert response.text == "198.51.100.9|True"

    def test_untrusted_forwarded_address_is_ignored(self, app):
        app.add_url_rule("/remote-address", view_func=lambda: request.remote_addr)
        response = app.test_client().get(
            "/remote-address", headers={"X-Forwarded-For": "198.51.100.9"}
        )
        assert response.text == "127.0.0.1"

    def test_redis_url_enables_server_side_sessions(self, monkeypatch):
        import redis
        from flask_session.redis.redis import RedisSessionInterface
        from app import create_app

        sentinel = redis.Redis(host="redis.example", port=6379, db=2)
        monkeypatch.setenv("REDIS_URL", "redis://redis.example:6379/2")
        monkeypatch.setattr(redis.Redis, "from_url", lambda url: sentinel)
        application = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": TEST_SECRET,
            }
        )
        assert isinstance(application.session_interface, RedisSessionInterface)
        assert application.config["SESSION_REDIS"] is sentinel
        from limits.storage import RedisStorage

        assert isinstance(application.extensions["rate_limiter"].storage, RedisStorage)

    def test_secure_cookie_flag_can_be_enabled(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
        application = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": TEST_SECRET,
                "RATELIMIT_ENABLED": False,
            }
        )
        response = application.test_client().get("/")
        assert "Secure" in response.headers["Set-Cookie"]

    def test_invalid_trusted_proxy_count_fails_fast(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("TRUSTED_PROXY_COUNT", "-1")
        with pytest.raises(ValueError, match="非負整數"):
            create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})
