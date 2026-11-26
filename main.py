from collections import OrderedDict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timezone
import queue
import random
import sqlite3
import string
import threading
import time

DB_FILE = "links.db"

# Step 3: cache
CACHE_SIZE = 100
cache = OrderedDict()
cache_hits = 0
cache_misses = 0

# Step 4: queue for clicks
click_queue = queue.Queue()
batches_written = 0
clicks_written = 0
write_lock = threading.Lock()


def run(sql, params=()):
    # Step 6: wait up to 5 seconds if the database is busy, instead of failing
    conn = sqlite3.connect(DB_FILE, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


run("""
    CREATE TABLE IF NOT EXISTS links (
        code        TEXT PRIMARY KEY,
        long_url    TEXT NOT NULL,
        clicks      INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL
    )
""")
# Step 6: index on long_url so we can quickly check "was this URL already shortened?"
run("CREATE INDEX IF NOT EXISTS idx_links_long_url ON links(long_url)")


def drain_queue():
    """Take every click waiting in the queue and count them per code."""
    batch = {}
    while True:
        try:
            code = click_queue.get_nowait()
        except queue.Empty:
            return batch
        batch[code] = batch.get(code, 0) + 1


def save_batch(batch):
    """Save a batch of clicks. Step 6: retry up to 3 times if the database is busy."""
    global batches_written, clicks_written
    if not batch:
        return
    with write_lock:
        for code, count in batch.items():
            for attempt in range(3):
                try:
                    run("UPDATE links SET clicks = clicks + ? WHERE code = ?", (count, code))
                    clicks_written += count
                    break
                except sqlite3.OperationalError:
                    time.sleep(0.5)
        batches_written += 1


def click_worker():
    """Background worker: every 2 seconds, save whatever clicks are waiting."""
    while True:
        time.sleep(2)
        save_batch(drain_queue())


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=click_worker, daemon=True).start()
    yield
    # Step 6: on shutdown, save clicks still waiting in the queue (don't lose them)
    save_batch(drain_queue())


app = FastAPI(title="URL Shortener", lifespan=lifespan)


class ShortenRequest(BaseModel):
    url: HttpUrl  # Step 6: must be a real http(s) URL, "string" is rejected


def make_code(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def get_long_url(code):
    global cache_hits, cache_misses
    if code in cache:
        cache_hits += 1
        cache.move_to_end(code)
        return cache[code]
    cache_misses += 1
    row = run("SELECT long_url FROM links WHERE code = ?", (code,))
    if row is None:
        return None
    cache[code] = row["long_url"]
    if len(cache) > CACHE_SIZE:
        cache.popitem(last=False)
    return row["long_url"]


@app.post("/shorten")
def shorten(request: ShortenRequest):
    long_url = str(request.url)
    # Step 6: same URL twice -> return the same code (idempotent)
    existing = run("SELECT code FROM links WHERE long_url = ?", (long_url,))
    if existing:
        return {"short_code": existing["code"], "long_url": long_url, "already_existed": True}
    while True:
        code = make_code()
        if run("SELECT 1 FROM links WHERE code = ?", (code,)) is None:
            break
    run(
        "INSERT INTO links (code, long_url, created_at) VALUES (?, ?, ?)",
        (code, long_url, datetime.now(timezone.utc).isoformat()),
    )
    return {"short_code": code, "long_url": long_url, "already_existed": False}


@app.get("/health")
def health():
    run("SELECT 1")  # proves the database is reachable
    return {"status": "ok"}


@app.get("/cache-stats")
def cache_stats():
    return {"hits": cache_hits, "misses": cache_misses, "cached_links": len(cache)}


@app.get("/queue-stats")
def queue_stats():
    return {
        "waiting_in_queue": click_queue.qsize(),
        "batches_written": batches_written,
        "clicks_written": clicks_written,
    }


@app.get("/stats/{code}")
def stats(code: str):
    row = run("SELECT * FROM links WHERE code = ?", (code,))
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    return dict(row)


@app.get("/{code}")
def go(code: str):
    long_url = get_long_url(code)
    if long_url is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    click_queue.put(code)
    return RedirectResponse(long_url)