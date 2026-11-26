from collections import OrderedDict
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import queue
import random
import sqlite3
import string
import threading
import time

app = FastAPI(title="URL Shortener")

DB_FILE = "links.db"

# Step 3: cache
CACHE_SIZE = 100
cache = OrderedDict()
cache_hits = 0
cache_misses = 0

# Step 4: queue for clicks (saved to the database in batches)
click_queue = queue.Queue()
batches_written = 0
clicks_written = 0


def run(sql, params=()):
    conn = sqlite3.connect(DB_FILE)
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


def click_worker():
    """Background worker: collects clicks for 2 seconds, then saves them in one go."""
    global batches_written, clicks_written
    while True:
        first = click_queue.get()  # wait until at least one click arrives
        batch = {first: 1}
        time.sleep(2)  # collect more clicks for 2 seconds
        while True:
            try:
                code = click_queue.get_nowait()
            except queue.Empty:
                break
            batch[code] = batch.get(code, 0) + 1
        for code, count in batch.items():
            run("UPDATE links SET clicks = clicks + ? WHERE code = ?", (count, code))
            clicks_written += count
        batches_written += 1


threading.Thread(target=click_worker, daemon=True).start()


class ShortenRequest(BaseModel):
    url: str


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
    while True:
        code = make_code()
        if run("SELECT 1 FROM links WHERE code = ?", (code,)) is None:
            break
    run(
        "INSERT INTO links (code, long_url, created_at) VALUES (?, ?, ?)",
        (code, request.url, datetime.now(timezone.utc).isoformat()),
    )
    return {"short_code": code, "long_url": request.url}


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
    click_queue.put(code)  # just drop the click in the queue, don't wait for the DB
    return RedirectResponse(long_url)