FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser && chown -R appuser:appuser /app

USER appuser

COPY --chown=appuser:appuser . .

ENV PORT=5000 \
    FLASK_DEBUG=false \
    ENABLE_HSTS=false \
    SESSION_COOKIE_SECURE=false \
    TRUSTED_PROXY_COUNT=0 \
    GUNICORN_WORKERS=2 \
    LOG_LEVEL=INFO

EXPOSE 5000

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS} --access-logfile - --error-logfile - app:app"]
