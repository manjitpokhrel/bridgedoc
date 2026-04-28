import asyncio
import httpx
from dataclasses import dataclass
from typing import Optional, Callable
import os

TMT_BASE_URL = os.getenv("TMT_BASE_URL", "https://tmt.ilprl.ku.edu.np")


@dataclass
class TranslationResult:
    original: str
    translated: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None


DIRECTION_MAP = {
    "en→ne":     ("en",  "ne"),
    "en→tamang": ("en",  "tmg"),
    "ne→en":     ("ne",  "en"),
    "ne→tamang": ("ne",  "tmg"),
    "tamang→en": ("tmg", "en"),
    "tamang→ne": ("tmg", "ne"),
}

REVERSE_MAP = {
    "en→ne":     "ne→en",
    "en→tamang": "tamang→en",
    "ne→en":     "en→ne",
    "ne→tamang": "tamang→ne",
    "tamang→en": "en→tamang",
    "tamang→ne": "ne→tamang",
}


class TMTClient:

    def __init__(self, api_key: str, max_retries: int = 3, concurrency: int = 5):
        self.api_key = api_key
        self.max_retries = max_retries
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    async def translate_one(
        self,
        sentence: str,
        direction: str,
        client: httpx.AsyncClient,
    ) -> TranslationResult:

        if not sentence.strip():
            src, tgt = DIRECTION_MAP.get(direction, ("en", "ne"))
            return TranslationResult(
                original=sentence, translated=sentence,
                source_lang=src, target_lang=tgt, success=True
            )

        src, tgt = DIRECTION_MAP.get(direction, ("en", "ne"))

        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        f"{TMT_BASE_URL}/lang-translate",
                        json={
                            "text": sentence,
                            "src_lang": src,
                            "tgt_lang": tgt,
                        },
                        headers=self.headers,
                        timeout=30.0,
                    )

                    # API always returns 200
                    # Check message_type field instead
                    data = response.json()

                    if data.get("message_type") == "SUCCESS":
                        return TranslationResult(
                            original=sentence,
                            translated=data.get("output", sentence),
                            source_lang=src,
                            target_lang=tgt,
                            success=True,
                        )
                    else:
                        # API returned FAIL
                        error_msg = data.get("message", "Translation failed")

                        # Don't retry on auth or input errors
                        if any(x in error_msg.lower() for x in [
                            "invalid api token",
                            "authorization",
                            "required",
                            "must be different",
                        ]):
                            return TranslationResult(
                                original=sentence, translated=sentence,
                                source_lang=src, target_lang=tgt,
                                success=False, error=error_msg
                            )

                        # Retry on server errors
                        if attempt == self.max_retries - 1:
                            return TranslationResult(
                                original=sentence, translated=sentence,
                                source_lang=src, target_lang=tgt,
                                success=False, error=error_msg
                            )
                        await asyncio.sleep(2 ** attempt)

                except httpx.TimeoutException:
                    if attempt == self.max_retries - 1:
                        return TranslationResult(
                            original=sentence, translated=sentence,
                            source_lang=src, target_lang=tgt,
                            success=False, error="Timeout"
                        )
                    await asyncio.sleep(2 ** attempt)

                except Exception as e:
                    if attempt == self.max_retries - 1:
                        return TranslationResult(
                            original=sentence, translated=sentence,
                            source_lang=src, target_lang=tgt,
                            success=False, error=str(e)
                        )
                    await asyncio.sleep(2 ** attempt)

    async def _translate_indexed(
        self,
        index: int,
        sentence: str,
        direction: str,
        client: httpx.AsyncClient,
    ) -> tuple:
        result = await self.translate_one(sentence, direction, client)
        return (index, result)

    async def translate_batch(
        self,
        sentences: list[str],
        direction: str,
        progress_callback: Optional[Callable] = None,
    ) -> list[TranslationResult]:

        async with httpx.AsyncClient() as client:
            indexed = list(enumerate(sentences))
            tasks = [
                self._translate_indexed(i, s, direction, client)
                for i, s in indexed
            ]

            results_indexed = []
            completed = 0

            for coro in asyncio.as_completed(tasks):
                result = await coro
                results_indexed.append(result)
                completed += 1
                if progress_callback:
                    await progress_callback(completed, len(sentences))

        results_indexed.sort(key=lambda x: x[0])
        return [r for _, r in results_indexed]

    def get_reverse_direction(self, direction: str) -> str:
        return REVERSE_MAP.get(direction, direction)