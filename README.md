# URL Shortener

A URL shortening service (similar to bit.ly) built with FastAPI, designed around core system design concerns: storage, caching, asynchronous processing, scaling and reliability.

## Features
- Create short codes for long URLs (`POST /shorten`)
- Redirect short codes to the original URL (`GET /{code}`)
- Per-link click statistics (`GET /stats/{code}`)
- Health and monitoring endpoints (`/health`, `/cache-stats`, `/queue-stats`)

## Architecture

| Layer | Implementation |
|-------|----------------|
| API | FastAPI REST endpoints with request validation |
| Storage | SQLite; `code` as primary key, index on `long_url` |
| Caching | In-memory LRU cache in front of the database for redirect lookups |
| Async processing | Click events queued and written in batches by a background worker |
| Scaling | Stateless request handling; multiple instances can share the database |
| Reliability | URL validation, idempotent link creation, retries on database contention, graceful shutdown that flushes pending events, health check |

## Design decisions and trade-offs

| Decision | Benefit | Cost | At larger scale |
|----------|---------|------|-----------------|
| SQLite instead of PostgreSQL | Zero setup, single file | Limited to one machine | PostgreSQL shared across instances |
| In-memory cache per instance | Very fast redirects, no extra service | Each instance holds its own cache; cleared on restart | Shared cache (Redis) |
| Queue + batched writes for clicks | Far fewer database writes | Click counts are eventually consistent (up to 2s behind) | Managed queue or Kafka |
| Random 6-character codes | Hard to guess; ~56 billion combinations | Requires a collision check | Pre-generated code pool or ID-based encoding |
| Same URL returns the same code | No duplicates; safe to retry | No per-sharer analytics | Per-user codes if needed |

## Run locally

```bash
pip install fastapi uvicorn
uvicorn main:app --reload```

Then open `http://127.0.0.1:8000/docs` to try the API.

## Tech
Python · FastAPI · SQLite
