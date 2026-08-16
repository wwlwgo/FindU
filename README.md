# FindU

找到你，黑客松寻觅队友。

## Backend Development

The backend uses Python 3.11+, FastAPI, SQLAlchemy, and SQLite. Replay is the stable demo path:
the frontend can create a profile, browse broadcasts, trigger one Agent action at a time, consume
filtered SSE events, and submit human confirmation without any external API key.

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

The demo activity is `act_demo`. After creating and confirming a participant profile, use
`POST /api/v1/activities/act_demo/runs` with `{"mode":"replay","replayTrackId":"alice_bob_mutual_intent","maxSteps":1}`.
Call it once per Agent action; the server persists the conversation and publishes SSE events.
`alice_carol_decline` is the short rejection track. A live run without a configured provider returns
`PROVIDER_UNAVAILABLE`; a live request that includes a replay track automatically falls back to replay.

The recording endpoint accepts audio in memory and currently returns `PROVIDER_UNAVAILABLE` when no
speech provider is configured. Use `POST /participants/{id}/profile-draft` with the preset transcript
fallback. Raw audio and full transcripts are not written to logs or persistent storage.

Copy `.env.example` to `.env` to override development defaults. Never put API keys or GitHub tokens
in source files or commit them to the repository.
