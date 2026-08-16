# FindU

找到你，黑客松寻觅队友。

## Backend Development

The backend uses Python 3.11+, FastAPI, and SQLite. It currently includes the phase 1 service
foundation: health checks, CORS configuration, request IDs, and a consistent API error envelope.

```bash
uv venv --python 3.11
uv sync --group dev
uv run uvicorn app.main:app --reload
```

The service listens on `http://127.0.0.1:8000` by default.

```bash
curl http://127.0.0.1:8000/api/v1/health
uv run pytest
```

Copy `.env.example` to `.env` to override development defaults. Never put API keys or GitHub tokens
in source files or commit them to the repository.
