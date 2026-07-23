# TenderShield backend — FastAPI modular monolith.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]" || pip install -e .
COPY . .

EXPOSE 8000
# Run migrations then serve. TS_DATABASE_URL must point at Postgres in prod.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
