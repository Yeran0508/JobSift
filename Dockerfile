FROM python:3.12.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY config ./config
COPY scripts ./scripts
RUN pip install --no-cache-dir .

RUN addgroup --system app && adduser --system --ingroup app --home /nonexistent app
USER app

EXPOSE 8000

CMD ["uvicorn", "jobsift.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test

USER root
RUN pip install --no-cache-dir ".[dev]"
USER app

ENV RUFF_CACHE_DIR=/tmp/ruff_cache \
    COVERAGE_FILE=/tmp/.coverage
