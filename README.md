# VibeCodingOsho

以 Flask 與 Jinja 製作的奧修禪卡線上抽卡示範網站。抽卡結果與最多 50 筆歷史會保存在使用者 session；設定 `REDIS_URL` 時，session 與限流計數共用 Redis，適合多個 Gunicorn worker。

![Osho01](./images/Osho01.png)

## 本機開發

需要 Python 3.11 以上版本。建立並啟用虛擬環境後，安裝依賴：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

設定只供本機使用的 Flask 金鑰並啟動：

```powershell
$env:FLASK_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

開啟 [http://127.0.0.1:5000](http://127.0.0.1:5000)。按 `Ctrl+C` 停止開發伺服器。本機未設定 `REDIS_URL` 時，Flask 使用簽章 Cookie session；勿將本機金鑰用於正式環境。

## Docker Compose

1. 複製環境範例：`Copy-Item .env.example .env`。
2. 產生金鑰：`python -c "import secrets; print(secrets.token_hex(32))"`，將結果填入 `.env` 的 `FLASK_SECRET_KEY`。
3. 啟動：`docker compose up --build`。
4. 開啟 [http://localhost:5000](http://localhost:5000)。按 `Ctrl+C` 停止；執行 `docker compose down` 可移除容器。

Compose 會等待 Redis 健康檢查通過，再以 Gunicorn 啟動兩個 worker。Redis 只供 Compose 內部服務使用，不會發布到主機連接埠；session 與限流計數在 worker 間共用。

### HTTPS 反向代理

只有在 HTTPS 已由反向代理終止，且代理會覆寫 `X-Forwarded-For` 和 `X-Forwarded-Proto` 時，才在 `.env` 設定 `ENABLE_HSTS=true`、`SESSION_COOKIE_SECURE=true` 及 `TRUSTED_PROXY_COUNT`。後者應設為請求實際經過的可信代理數量；不要讓用戶端直接連到可偽造這些標頭的應用程式。

## 專案結構

- `app.py`：Flask app factory、路由、抽卡、session、CSRF、限流與安全標頭
- `templates/`：Jinja 頁面模板
- `static/css/styles.css`：網站樣式
- `data/cards.json`：預置卡牌資料
- `tests/test_app.py`：路由、安全設定與 session 流程測試
- `Dockerfile`、`docker-compose.yml`：Gunicorn、Redis 與容器部署設定

正式環境請提供隨機 `FLASK_SECRET_KEY`，不要啟用 `FLASK_DEBUG`。
