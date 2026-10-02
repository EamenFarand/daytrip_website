FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3.12

COPY listener.py ./
RUN useradd --system --uid 10001 lifts && mkdir /data && chown lifts /data
USER lifts

ENV STATE_FILE=/data/state.json PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python", "listener.py"]
