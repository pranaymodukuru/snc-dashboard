FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
# Must match the Railway Volume mount path (see README) so the SQLite DB
# lands on persistent storage instead of the ephemeral container filesystem.
ENV DATA_DIR=/data
COPY pyproject.toml .
RUN uv sync --no-dev
COPY api/ .
EXPOSE 8000
# Bind to :: (dual-stack) — Railway's private network is IPv6-only, so the
# dashboard's API_URL=*.railway.internal calls fail if uvicorn only listens on
# IPv4 (0.0.0.0). :: serves both IPv6 (private net) and IPv4 (public edge).
CMD ["sh", "-c", "uv run uvicorn main:app --host :: --port ${PORT:-8000}"]
