import json
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_db(monkeypatch):
    """Point storage at a temporary SQLite DB, init tables, clean up after."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr("config.DATABASE_PATH", path)
    # Re-import after patching so storage picks up the new path
    import config
    monkeypatch.setattr("services.storage.DATABASE_PATH", path)
    from services.storage import init_db
    init_db()
    yield path
    os.unlink(path)


@pytest.fixture
def sample_schema():
    """A realistic raw OpenAPI schema dict modeled on flux-schnell."""
    return {
        "components": {
            "schemas": {
                "Input": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Text prompt",
                            "x-order": 0,
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Random seed",
                            "x-order": 4,
                        },
                        "num_outputs": {
                            "type": "integer",
                            "default": 1,
                            "minimum": 1,
                            "maximum": 4,
                            "x-order": 2,
                        },
                        "aspect_ratio": {
                            "allOf": [{"$ref": "#/components/schemas/aspect_ratio"}],
                            "default": "1:1",
                            "description": "Aspect ratio",
                            "x-order": 1,
                        },
                        "go_fast": {
                            "type": "boolean",
                            "default": True,
                            "x-order": 8,
                        },
                        "cfg": {
                            "type": "number",
                            "default": 5.0,
                            "minimum": 1.0,
                            "maximum": 10.0,
                            "x-order": 3,
                        },
                        "image": {
                            "type": "string",
                            "format": "uri",
                            "description": "Input image",
                            "x-order": 9,
                        },
                        "image_input": {
                            "type": "array",
                            "items": {"type": "string", "format": "uri"},
                            "default": [],
                            "x-order": 10,
                        },
                    },
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                },
            }
        }
    }


@pytest.fixture
def client(tmp_db, sample_schema):
    """FastAPI TestClient with mocked external APIs."""
    schema_json = json.dumps(sample_schema)

    # Pre-cache the schema so model_form route doesn't call Replicate
    from services.storage import cache_schema
    cache_schema("black-forest-labs/flux-schnell", schema_json)

    mock_fetch = AsyncMock(return_value=sample_schema)
    mock_run = AsyncMock(return_value="https://replicate.delivery/fake/out.webp")

    with patch("services.replicate_client.fetch_schema", mock_fetch), \
         patch("services.replicate_client.run_model", mock_run):
        from main import app
        with TestClient(app) as c:
            yield c
