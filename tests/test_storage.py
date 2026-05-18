"""Unit tests for services/storage.py — SQLite CRUD helpers."""

import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from services import storage


def test_init_db_creates_tables(tmp_db):
    conn = sqlite3.connect(tmp_db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    conn.close()
    assert "generations" in tables
    assert "model_schemas" in tables
    assert "sweep_runs" in tables


def test_create_sweep_run(tmp_db):
    run_id = storage.create_sweep_run(
        "test/model", {"prompt": "hello"}, {"input_name": "seed", "values": [1, 2]}
    )
    assert isinstance(run_id, int)
    assert run_id >= 1


def test_create_and_get_generation(tmp_db):
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {"prompt": "test"}, 0, "seed=42")

    gen = storage.get_generation(gen_id)
    assert gen is not None
    assert gen["sweep_run_id"] == run_id
    assert gen["axis_position"] == 0
    assert gen["label"] == "seed=42"
    assert gen["status"] == "pending"
    assert gen["output_url"] is None
    assert json.loads(gen["inputs"]) == {"prompt": "test"}


def test_get_generation_not_found(tmp_db):
    assert storage.get_generation(99999) is None


def test_update_generation_status_complete(tmp_db):
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")

    storage.update_generation_status(
        gen_id, "complete",
        output_url="https://example.com/img.webp",
        generation_ms=1234,
    )

    gen = storage.get_generation(gen_id)
    assert gen["status"] == "complete"
    assert gen["output_url"] == "https://example.com/img.webp"
    assert gen["generation_ms"] == 1234
    assert gen["error"] is None


def test_update_generation_status_failed(tmp_db):
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")

    storage.update_generation_status(
        gen_id, "failed",
        error="Rate limited",
        generation_ms=50,
    )

    gen = storage.get_generation(gen_id)
    assert gen["status"] == "failed"
    assert gen["error"] == "Rate limited"
    assert gen["output_url"] is None


def test_get_generations_for_sweep_ordered(tmp_db):
    run_id = storage.create_sweep_run("test/model", {}, {})
    # Insert out of order
    storage.create_generation(run_id, {}, 2, "c")
    storage.create_generation(run_id, {}, 0, "a")
    storage.create_generation(run_id, {}, 1, "b")

    gens = storage.get_generations_for_sweep(run_id)
    assert len(gens) == 3
    assert [g["axis_position"] for g in gens] == [0, 1, 2]
    assert [g["label"] for g in gens] == ["a", "b", "c"]


def test_cache_schema_roundtrip(tmp_db):
    storage.cache_schema("test/model", '{"test": true}')
    cached = storage.get_cached_schema("test/model")
    assert cached == '{"test": true}'


def test_cache_schema_miss(tmp_db):
    assert storage.get_cached_schema("nonexistent/model") is None


def test_cache_schema_upsert(tmp_db):
    storage.cache_schema("test/model", '{"v": 1}')
    storage.cache_schema("test/model", '{"v": 2}')
    cached = storage.get_cached_schema("test/model")
    assert cached == '{"v": 2}'


def test_cache_schema_expired(tmp_db, monkeypatch):
    storage.cache_schema("test/model", '{"old": true}')

    # Monkey-patch the TTL to 0 so the entry is immediately expired
    monkeypatch.setattr("services.storage.SCHEMA_CACHE_TTL_SECONDS", 0)
    time.sleep(0.01)

    assert storage.get_cached_schema("test/model") is None
