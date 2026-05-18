"""SQLite DDL + synchronous CRUD helpers.

Every function opens its own short-lived connection.
Call from async routes via asyncio.to_thread().
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from config import DATABASE_PATH, SCHEMA_CACHE_TTL_SECONDS


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sweep_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            model_slug  TEXT NOT NULL,
            fixed_inputs TEXT NOT NULL,
            axis_config  TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sweep_run_id  INTEGER NOT NULL REFERENCES sweep_runs(id),
            inputs        TEXT NOT NULL,
            axis_position INTEGER NOT NULL,
            label         TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending'
                          CHECK(status IN ('pending','running','complete','failed')),
            output_url    TEXT,
            error         TEXT,
            generation_ms INTEGER,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_schemas (
            slug        TEXT PRIMARY KEY,
            schema_json TEXT NOT NULL,
            cached_at   TEXT NOT NULL
        );
    """)
    conn.close()


# ── sweep_runs ──────────────────────────────────────────────────────

def create_sweep_run(model_slug: str, fixed_inputs: dict, axis_config: dict) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sweep_runs (model_slug, fixed_inputs, axis_config, created_at) VALUES (?, ?, ?, ?)",
        (model_slug, json.dumps(fixed_inputs), json.dumps(axis_config), _now()),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


# ── generations ─────────────────────────────────────────────────────

def create_generation(sweep_run_id: int, inputs: dict, axis_position: int, label: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO generations (sweep_run_id, inputs, axis_position, label, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (sweep_run_id, json.dumps(inputs), axis_position, label, _now()),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_generation_status(
    gen_id: int,
    status: str,
    output_url: str | None = None,
    error: str | None = None,
    generation_ms: int | None = None,
) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE generations SET status=?, output_url=?, error=?, generation_ms=? WHERE id=?",
        (status, output_url, error, generation_ms, gen_id),
    )
    conn.commit()
    conn.close()


def get_generation(gen_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM generations WHERE id=?", (gen_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_generations_for_sweep(sweep_run_id: int) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM generations WHERE sweep_run_id=? ORDER BY axis_position",
        (sweep_run_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── model_schemas (24h cache) ──────────────────────────────────────

def get_cached_schema(slug: str) -> str | None:
    conn = _connect()
    row = conn.execute("SELECT schema_json, cached_at FROM model_schemas WHERE slug=?", (slug,)).fetchone()
    conn.close()
    if row is None:
        return None
    cached_at = datetime.fromisoformat(row["cached_at"])
    age = (datetime.now(timezone.utc) - cached_at).total_seconds()
    if age > SCHEMA_CACHE_TTL_SECONDS:
        return None
    return row["schema_json"]


def cache_schema(slug: str, schema_json: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO model_schemas (slug, schema_json, cached_at) VALUES (?, ?, ?) "
        "ON CONFLICT(slug) DO UPDATE SET schema_json=excluded.schema_json, cached_at=excluded.cached_at",
        (slug, schema_json, _now()),
    )
    conn.commit()
    conn.close()


# ── helpers ─────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
