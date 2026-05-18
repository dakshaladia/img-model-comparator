"""Unit tests for services/replicate_client.py — output shape handling."""

import asyncio
from unittest.mock import AsyncMock, patch

from services.replicate_client import run_model


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_run_model_string_output():
    with patch("replicate.async_run", new_callable=AsyncMock) as mock:
        mock.return_value = "https://example.com/image.webp"
        result = _run(run_model("test/model", {"prompt": "test"}))
        assert result == "https://example.com/image.webp"


def test_run_model_list_output():
    with patch("replicate.async_run", new_callable=AsyncMock) as mock:
        mock.return_value = [
            "https://example.com/img1.webp",
            "https://example.com/img2.webp",
        ]
        result = _run(run_model("test/model", {"prompt": "test"}))
        assert result == "https://example.com/img1.webp"


def test_run_model_fileoutput_object():
    """FileOutput objects should be converted to string (gives the URL)."""
    class FakeFileOutput:
        def __init__(self, url):
            self.url = url
        def __str__(self):
            return self.url

    with patch("replicate.async_run", new_callable=AsyncMock) as mock:
        mock.return_value = FakeFileOutput("https://example.com/file.webp")
        result = _run(run_model("test/model", {"prompt": "test"}))
        assert result == "https://example.com/file.webp"
