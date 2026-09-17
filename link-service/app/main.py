import logging
import os
import secrets
import string
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, HttpUrl, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("scalelink.link-service")
BASE62 = string.ascii_lowercase + string.ascii_uppercase + string.digits

def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value

def get_connection():
    return psycopg.connect(database_url(), connect_timeout=3, row_factory=dict_row)

def ensure_schema() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id BIGSERIAL PRIMARY KEY,
                short_code VARCHAR(16) NOT NULL UNIQUE,
                target_url TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.commit()

def database_ready() -> bool:
    try:
        ensure_schema()
        with get_connection() as connection:
            row = connection.execute("SELECT 1 AS healthy").fetchone()
        return bool(row and row["healthy"] == 1)
    except Exception:
        return False

class LinkCreate(BaseModel):
    target_url: HttpUrl

    @field_validator("target_url")
    @classmethod
    def validate_length(cls, value: HttpUrl) -> HttpUrl:
        if len(str(value)) > 2048:
            raise ValueError("target_url must not exceed 2048 characters")
        return value

class LinkOut(BaseModel):
    id: int
    short_code: str
    target_url: str
    public_url: str
    created_at: datetime

def categorize_user_agent(value: str | None) -> str:
    if not value:
        return "unknown"
    text = value.lower()
    if any(x in text for x in ("bot", "crawler", "spider", "slurp")):
        return "bot"
    if any(x in text for x in ("ipad", "tablet", "kindle")):
        return "tablet"
    if any(x in text for x in ("mobile", "iphone", "android")):
        return "mobile"
    if any(x in text for x in ("windows", "macintosh", "linux", "x11")):
        return "desktop"
    return "other"

async def record_click(link_id: int, referrer: str | None, user_agent: str) -> bool:
    analytics_url = os.getenv("ANALYTICS_SERVICE_URL")
    if not analytics_url:
        logger.warning("Analytics URL not configured; redirect continues")
        return False
    try:
        async with httpx.AsyncClient(timeout=0.75) as client:
            response = await client.post(
                analytics_url.rstrip("/") + "/api/events",
                json={"link_id": link_id, "referrer": referrer, "user_agent": user_agent},
            )
        if 200 <= response.status_code < 300:
            return True
        logger.warning("Analytics returned HTTP %s; redirect continues", response.status_code)
    except Exception as exc:
        logger.warning("Analytics unavailable (%s); redirect continues", exc)
    return False

@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        ensure_schema()
        logger.info("PostgreSQL schema ready")
    except Exception:
        logger.exception("PostgreSQL unavailable during startup")
    yield

app = FastAPI(title="ScaleLink Link Service", version="1.0.0", lifespan=lifespan)

def generate_short_code() -> str:
    return "".join(secrets.choice(BASE62) for _ in range(6))

def public_url(request: Request, short_code: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL") or str(request.base_url)
    return f"{base.rstrip('/')}/r/{short_code}"

def serialize(row: dict, request: Request) -> LinkOut:
    return LinkOut(
        id=row["id"],
        short_code=row["short_code"],
        target_url=row["target_url"],
        public_url=public_url(request, row["short_code"]),
        created_at=row["created_at"],
    )

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def browser_interface():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ScaleLink</title>
<style>body{font-family:Arial,sans-serif;max-width:760px;margin:50px auto;padding:0 20px}input{width:100%;box-sizing:border-box;padding:10px;margin:8px 0 12px}button{padding:9px 14px;cursor:pointer}#result{margin-top:20px;padding:12px;background:#f4f4f4}table{width:100%;border-collapse:collapse;margin-top:30px}th,td{text-align:left;padding:8px;border-bottom:1px solid #ddd;word-break:break-word}</style></head>
<body><h1>ScaleLink</h1><form id="form"><label for="url">Long URL:</label><input id="url" type="url" maxlength="2048" placeholder="https://www.example.com/very/long/url" required><button>Create Short Link</button></form><div id="result" hidden></div><h2>Links</h2><table><thead><tr><th>Short URL</th><th>Target</th><th></th></tr></thead><tbody id="links"></tbody></table>
<script>const form=document.getElementById("form"),input=document.getElementById("url"),result=document.getElementById("result"),links=document.getElementById("links");async function load(){const r=await fetch("/api/links"),data=await r.json();links.replaceChildren();for(const link of data){const row=document.createElement("tr"),aCell=document.createElement("td"),a=document.createElement("a"),t=document.createElement("td"),x=document.createElement("td"),b=document.createElement("button");a.href=link.public_url;a.textContent=link.public_url;aCell.appendChild(a);t.textContent=link.target_url;b.textContent="Delete";b.onclick=async()=>{await fetch("/api/links/"+link.id,{method:"DELETE"});await load()};x.appendChild(b);row.append(aCell,t,x);links.appendChild(row)}}form.addEventListener("submit",async e=>{e.preventDefault();const r=await fetch("/api/links",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({target_url:input.value})}),data=await r.json();result.hidden=false;if(!r.ok){result.textContent="Unable to create link.";return}result.replaceChildren();const a=document.createElement("a");a.href=data.public_url;a.textContent=data.public_url;result.append("Short URL: ",a);input.value="";await load()});load();</script></body></html>""")

@app.get("/health")
def health():
    return {"service": "link-service", "status": "healthy"}

@app.get("/ready")
def ready():
    if database_ready():
        return {"service": "link-service", "status": "ready"}
    return JSONResponse(status_code=503, content={"service": "link-service", "status": "not-ready"})

@app.post("/api/links", status_code=201, response_model=LinkOut)
def create_link(payload: LinkCreate, request: Request):
    target_url = str(payload.target_url)
    for _ in range(10):
        code = generate_short_code()
        try:
            with get_connection() as connection:
                row = connection.execute("""
                    INSERT INTO links (short_code, target_url)
                    VALUES (%s, %s)
                    RETURNING id, short_code, target_url, created_at
                """, (code, target_url)).fetchone()
                connection.commit()
            return serialize(row, request)
        except UniqueViolation:
            continue
        except Exception as exc:
            logger.exception("Unable to create link")
            raise HTTPException(status_code=500, detail="Unable to create link") from exc
    raise HTTPException(status_code=500, detail="Unable to allocate a unique short code")

@app.get("/api/links", response_model=list[LinkOut])
def list_links(request: Request):
    try:
        with get_connection() as connection:
            rows = connection.execute("SELECT id, short_code, target_url, created_at FROM links ORDER BY created_at DESC, id DESC").fetchall()
        return [serialize(row, request) for row in rows]
    except Exception as exc:
        logger.exception("Unable to retrieve links")
        raise HTTPException(status_code=500, detail="Unable to retrieve links") from exc

@app.get("/api/links/{link_id}", response_model=LinkOut)
def get_link(link_id: int, request: Request):
    try:
        with get_connection() as connection:
            row = connection.execute("SELECT id, short_code, target_url, created_at FROM links WHERE id = %s", (link_id,)).fetchone()
    except Exception as exc:
        logger.exception("Unable to retrieve link")
        raise HTTPException(status_code=500, detail="Unable to retrieve link") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Link not found")
    return serialize(row, request)

@app.delete("/api/links/{link_id}", status_code=204)
def delete_link(link_id: int):
    try:
        with get_connection() as connection:
            cursor = connection.execute("DELETE FROM links WHERE id = %s", (link_id,))
            deleted = cursor.rowcount
            connection.commit()
    except Exception as exc:
        logger.exception("Unable to delete link")
        raise HTTPException(status_code=500, detail="Unable to delete link") from exc
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    return Response(status_code=204)

@app.get("/r/{short_code}")
async def resolve_short_code(short_code: str, request: Request):
    try:
        with get_connection() as connection:
            row = connection.execute("SELECT id, target_url FROM links WHERE short_code = %s", (short_code,)).fetchone()
    except Exception as exc:
        logger.exception("Unable to resolve short code")
        raise HTTPException(status_code=500, detail="Unable to resolve link") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Short link not found")
    await record_click(
        link_id=row["id"],
        referrer=request.headers.get("referer"),
        user_agent=categorize_user_agent(request.headers.get("user-agent")),
    )
    return RedirectResponse(url=row["target_url"], status_code=307)
