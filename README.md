# URL Shortener: Learning System Design

A personal project to learn system design by building a URL shortener (like bit.ly) step by step.

AI coding agents can write code fast. Designing *how* a system fits together is still a human skill, and that's what this project is for.

## What it does
- Turn a long URL into a short code (`POST /shorten`)
- Redirect the short code to the original URL (`GET /{code}`)
- Count clicks (`GET /stats/{code}`)
- Health and monitoring pages (`/health`, `/cache-stats`, `/queue-stats`)

## Learning roadmap

| Step | Concept | What I built | Status |
|------|---------|--------------|--------|
| 1 | Client, server and API | FastAPI with 3 endpoints | ✅ |
| 2 | Databases | SQLite table with `code` as primary key | ✅ |
| 3 | Caching | In-memory LRU cache for redirects (hit/miss stats) | ✅ |
| 4 | Queues | Clicks go into a queue; a background worker saves them in batches | ✅ |
| 5 | Scaling | Ran 2 server copies: shared database, but separate caches | ✅ |
| 6 | Reliability | URL validation, idempotent shorten, DB retries, safe shutdown, health check | ✅ |
| 7 | Trade-offs | Documented below | ✅ |

## Design decisions and trade-offs

| Decision | What I gained | What I gave up | At bigger scale |
|----------|---------------|----------------|-----------------|
| **SQLite** instead of PostgreSQL | Zero setup, one file | Only works on one machine | PostgreSQL shared by all servers |
| **In-memory cache** per server | Very fast redirects, no extra service | Each server has its own cache; lost on restart | Redis as a shared cache |
| **Queue + batch writes** for clicks | Far fewer database writes | Click counts are up to 2 seconds behind (eventual consistency) | Kafka or a managed queue |
| **Random 6-character codes** | Hard to guess; 56 billion possible codes | Must check for collisions | Pre-generated code pool or ID-based encoding |
| **Same URL returns the same code** | No duplicates, safe to retry | Can't track clicks per person who shared it | Per-user codes if analytics needed |

## Tech
Python · FastAPI · SQLite · GitHub Codespaces