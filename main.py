from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import random
import string

app = FastAPI(title="URL Shortener")

# Step 1: store links in memory (a Python dictionary).
# Like a 2-column Excel sheet: short code -> long URL.
# In Step 2 we'll replace this with a real database.
links = {}
clicks = {}


class ShortenRequest(BaseModel):
    url: str


def make_code(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


# POST /shorten  ->  create a short link
@app.post("/shorten")
def shorten(request: ShortenRequest):
    code = make_code()
    links[code] = request.url
    clicks[code] = 0
    return {"short_code": code, "long_url": request.url}


# GET /{code}  ->  send the user to the original URL
@app.get("/{code}")
def go(code: str):
    if code not in links:
        raise HTTPException(status_code=404, detail="Short link not found")
    clicks[code] += 1
    return RedirectResponse(links[code])


# GET /stats/{code}  ->  how many times was it clicked?
@app.get("/stats/{code}")
def stats(code: str):
    if code not in links:
        raise HTTPException(status_code=404, detail="Short link not found")
    return {"short_code": code, "long_url": links[code], "clicks": clicks[code]}