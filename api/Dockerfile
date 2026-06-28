FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
# Must match the Railway Volume mount path (see README) so the SQLite DB
# lands on persistent storage instead of the ephemeral container filesystem.
ENV DATA_DIR=/app/data
COPY pyproject.toml .
RUN uv sync --no-dev
COPY api/ api/
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
