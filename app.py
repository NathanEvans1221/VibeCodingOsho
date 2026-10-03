import json
import logging
import os
import random
from datetime import datetime, timezone
from functools import lru_cache

from dotenv import load_dotenv
from flask import Flask, render_template, session, redirect, url_for, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# 載入 .env 檔案
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _trusted_proxy_count() -> int:
    value = os.environ.get("TRUSTED_PROXY_COUNT", "0")
    try:
        count = int(value)
    except ValueError as error:
        raise ValueError("TRUSTED_PROXY_COUNT 必須是非負整數") from error
    if count < 0:
        raise ValueError("TRUSTED_PROXY_COUNT 必須是非負整數")
    return count


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("vibecodingosho")

    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        raise ValueError("FLASK_SECRET_KEY 環境變數未設定，請設定後再啟動應用程式")

    redis_url = os.environ.get("REDIS_URL")
    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_PERMANENT=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_env_bool("SESSION_COOKIE_SECURE"),
    )
    if redis_url:
        from redis import Redis

        app.config.update(
            SESSION_TYPE="redis",
            SESSION_KEY_PREFIX="vibecodingosho:",
        )
        app.config["SESSION_REDIS"] = Redis.from_url(redis_url)
    if test_config:
        app.config.update(test_config)

    proxy_count = _trusted_proxy_count()
    if proxy_count:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count)

    if redis_url:
        Session(app)
    CSRFProtect(app)
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=redis_url or "memory://",
    )
    app.extensions["rate_limiter"] = limiter

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now(timezone.utc).year}

    @lru_cache(maxsize=1)
    def get_cards() -> list[dict]:
        """載入並快取卡牌資料。"""
        data_path = os.path.join(os.path.dirname(__file__), "data", "cards.json")
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("cards", [])
        except FileNotFoundError:
            raise RuntimeError(f"卡牌資料檔案不存在: {data_path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"卡牌資料 JSON 格式錯誤: {e}")

    def add_history(entry: dict) -> None:
        history = session.get("history", [])
        history.insert(0, entry)
        session["history"] = history[:50]

    @app.after_request
    def add_cache_headers(resp):  # type: ignore[override]
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-XSS-Protection"] = "1; mode=block"
        if _env_bool("ENABLE_HSTS"):
            resp.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        return resp

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return render_template(
            "error.html", code=429, message="請求過於頻繁，請稍後再試"
        ), 429

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="找不到您要的頁面"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template(
            "error.html", code=500, message="伺服器發生錯誤，請稍後再試"
        ), 500

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/draw", methods=["POST"])
    @limiter.limit("10 per minute")
    def draw():
        logger.info("使用者請求抽卡")
        cards = get_cards()
        if not cards:
            logger.warning("卡牌資料為空，導回首頁")
            return redirect(url_for("index"))

        card = random.choice(cards)
        entry = {
            "name": card.get("name"),
            "suit": card.get("suit"),
            "key": card.get("key"),
            "meaning": card.get("meaning"),
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        session["last_result"] = entry
        add_history(entry)
        logger.info("抽卡成功: %s", entry["name"])
        return redirect(url_for("result"))

    @app.route("/result")
    def result():
        result_entry = session.get("last_result")
        if not result_entry:
            return redirect(url_for("index"))
        return render_template("result.html", result=result_entry)

    @app.route("/history")
    def history():
        history_entries = session.get("history", [])
        return render_template("history.html", history=history_entries)

    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = _env_bool("FLASK_DEBUG")
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_mode,
        threaded=False,
    )
