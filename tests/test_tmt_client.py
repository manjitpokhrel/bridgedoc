import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.tmt_client import TMTClient, TranslationResult


def test_direction_map_complete():
    from core.tmt_client import DIRECTION_MAP, REVERSE_MAP
    assert "en→ne" in DIRECTION_MAP
    assert "tamang→ne" in DIRECTION_MAP
    assert len(DIRECTION_MAP) == 6
    assert len(REVERSE_MAP) == 6


def test_empty_sentence_skipped():
    client = TMTClient("fake_key")
    result = asyncio.run(
        _translate_empty(client)
    )
    assert result.success is True
    assert result.translated == ""


async def _translate_empty(client):
    import httpx
    async with httpx.AsyncClient() as c:
        return await client.translate_one("", "en→ne", c)


def test_reverse_direction():
    client = TMTClient("fake_key")
    assert client.get_reverse_direction("en→ne") == "ne→en"
    assert client.get_reverse_direction("tamang→en") == "en→tamang"