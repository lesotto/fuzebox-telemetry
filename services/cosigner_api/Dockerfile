FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      fastapi 'sqlalchemy[asyncio]>=2' alembic structlog httpx \
      pydantic uvicorn asyncpg

COPY services /app/services
COPY sdk-python /app/sdk-python

ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["uvicorn", "services.cosigner_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
