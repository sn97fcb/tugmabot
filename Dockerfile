FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/app/data/tugmabot.db

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /app/data \
    && useradd --create-home --uid 10001 botuser \
    && chown -R botuser:botuser /app

COPY --chown=botuser:botuser . .
COPY --chown=botuser:botuser docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

USER botuser
VOLUME ["/app/data"]
CMD ["./docker-entrypoint.sh"]
