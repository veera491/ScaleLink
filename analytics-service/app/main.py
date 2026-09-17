import os
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

def database_url():
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value

def get_connection():
    return psycopg.connect(database_url(), connect_timeout=3, row_factory=dict_row)

def ensure_schema():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS click_events (
                id BIGSERIAL PRIMARY KEY,
                link_id BIGINT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
                clicked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                referrer TEXT NULL,
                user_agent VARCHAR(32) NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_click_events_link_id ON click_events(link_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_click_events_clicked_at ON click_events(clicked_at)")
        conn.commit()

def database_ready():
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT 1 AS healthy").fetchone()
        return bool(row and row["healthy"] == 1)
    except Exception:
        return False

class EventCreate(BaseModel):
    link_id: int
    referrer: str | None = None
    user_agent: str | None = None

    @field_validator("link_id")
    @classmethod
    def positive_link_id(cls, value):
        if value <= 0:
            raise ValueError("link_id must be positive")
        return value

    @field_validator("user_agent")
    @classmethod
    def valid_user_agent(cls, value):
        if value is None:
            return value
        if value not in {"desktop","mobile","tablet","bot","other","unknown"}:
            raise ValueError("unsupported user_agent category")
        return value

@asynccontextmanager
async def lifespan(app):
    ensure_schema()
    yield

app = FastAPI(title="ScaleLink Analytics Service", version="1.0.0", lifespan=lifespan)

@app.get("/", include_in_schema=False)
def root():
    return {"service":"analytics-service","status":"running"}

@app.get("/health")
def health():
    return {"service":"analytics-service","status":"healthy"}

@app.get("/ready")
def ready():
    if database_ready():
        return {"service":"analytics-service","status":"ready"}
    return JSONResponse(status_code=503, content={"service":"analytics-service","status":"not-ready"})

@app.post("/api/events", status_code=201)
def create_event(payload: EventCreate):
    try:
        with get_connection() as conn:
            exists = conn.execute("SELECT 1 FROM links WHERE id=%s", (payload.link_id,)).fetchone()
            if not exists:
                raise HTTPException(status_code=422, detail="Invalid link_id")
            row = conn.execute("""
                INSERT INTO click_events (link_id, referrer, user_agent)
                VALUES (%s,%s,%s)
                RETURNING id, link_id, clicked_at, referrer, user_agent
            """, (payload.link_id, payload.referrer, payload.user_agent)).fetchone()
            conn.commit()
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to record click event") from exc

@app.get("/api/stats/{link_id}")
def get_stats(link_id: int):
    try:
        with get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*)::BIGINT AS total_clicks, MAX(clicked_at) AS last_clicked_at
                FROM click_events WHERE link_id=%s
            """, (link_id,)).fetchone()
        return {"link_id":link_id,"total_clicks":row["total_clicks"],"last_clicked_at":row["last_clicked_at"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to retrieve statistics") from exc
