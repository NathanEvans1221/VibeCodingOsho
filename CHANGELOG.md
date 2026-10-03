# 變更紀錄

遵循 Keep a Changelog 格式。

## [Unreleased]

### 新增
- 加入抽卡 session、CSRF、代理信任、安全標頭與 Redis session 的行為測試。

### 修正
- 抽卡僅接受 POST，避免 GET 請求觸發狀態變更。
- 修正限流器生命週期，避免抽卡請求遇到 limiter 已回收錯誤。
- 讓正式容器使用 Gunicorn、Redis session 與 Redis 限流儲存，並等待 Redis 健康檢查通過。
- 只在啟用 HTTPS 部署設定時送出 HSTS；僅於設定可信代理數量時信任轉送 IP／協定標頭。
- 更新 Flask-Session 至相容 Flask 3 與 Werkzeug 3 的版本，並補上遺漏的 python-dotenv 依賴。

### 安全性
- 移除 Docker 映像內的預設弱 Secret Key，Compose 在 Secret Key 未設定時會停止啟動。
- 排除 Docker build context 中的 `.env`，避免將本機密鑰複製進映像。
- Redis 不再發布至主機連接埠。
