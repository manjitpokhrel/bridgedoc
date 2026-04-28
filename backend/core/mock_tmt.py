import asyncio
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class TranslationResult:
    original: str
    translated: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None


class MockTMTClient:
    """
    Simulates sentence-level translation.
    Used for full pipeline testing BEFORE real API.
    """

    def __init__(self, delay: float = 0.05):
        self.delay = delay  # simulate latency

    async def translate_batch(
        self,
        sentences: list[str],
        direction: str,
        progress_callback: Optional[Callable] = None,
    ):
        results = []
        total = len(sentences)

        for i, sentence in enumerate(sentences):
            await asyncio.sleep(self.delay)

            # Mock translation behavior
            translated = f"[{direction}] {sentence[::-1]}"

            results.append(
                TranslationResult(
                    original=sentence,
                    translated=translated,
                    source_lang=direction.split("→")[0],
                    target_lang=direction.split("→")[1],
                    success=True,
                )
            )

            if progress_callback:
                await progress_callback(i + 1, total)

        return results

    def get_reverse_direction(self, direction: str):
        src, tgt = direction.split("→")
        return f"{tgt}→{src}"