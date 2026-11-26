from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import random
import sqlite3
import string

app = FastAPI(title="URL Shortener")

# Step 2: store links in a SQLite database file instead of memory.
# The data now survives server restarts.
DB_FILE = "links.db"


def run(sql, params=()):
    """Run one SQL statement and return the first row (or None)."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # saves (commits) the change automatically
            return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


# Create the table once, if it doesn't exist yet.
# code is the PRIMARY KEY: unique, and indexed for fast lookups.
run("""
    CREATE TABLE IF NOT EXISTS links (
        code        TEXT PRIMARY KEY,
        long_url    TEXT NOT NULL,
        clicks      INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL
    )
""")


class ShortenRequest(BaseModel):
    url: str


def make_code(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


# POST /shorten  ->  create a short link
@app.post("/shorten")
def shorten(request: ShortenRequest):
    # Keep generating until we get a code that isn't already used
    while True:
        code = make_code()
        if run("SELECT 1 FROM links WHERE code = ?", (code,)) is None:
            break
    run(
        "INSERT INTO links (code, long_url, created_at) VALUES (?, ?, ?)",
        (code, request.url, datetime.now(timezone.utc).isoformat()),
    )
    return {"short_code": code, "long_url": request.url}


# GET /{code}  ->  send the user to the original URL
@app.get("/{code}")
def go(code: str):
    row = run("SELECT long_url FROM links WHERE code = ?", (code,))
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    run("UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code,))
    return RedirectResponse(row["long_url"])


# GET /stats/{code}  ->  how many times was it clicked?
@app.get("/stats/{code}")
def stats(code: str):
    row = run("SELECT * FROM links WHERE code = ?", (code,))
    if row is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    return dict(row)