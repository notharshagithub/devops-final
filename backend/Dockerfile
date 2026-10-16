FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# System deps for psycopg + healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

# Non-root runtime user (M4 requirement)
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

# Run migrations then start API (fails fast if DB unreachable)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
