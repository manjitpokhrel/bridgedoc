from typing import Optional
from dataclasses import dataclass


@dataclass
class QualityResult:
    original: str
    translated: str
    back_translated: str
    score: float
    flagged: bool


class TranslationQualityChecker:
    """
    Back-translation quality verification.
    Translates A→B, then B→A, compares with original.
    """

    FLAG_THRESHOLD = 0.4

    def __init__(self, tmt_client):
        self.client = tmt_client

    async def check_batch(
        self,
        originals: list[str],
        translations: list[str],
        forward_direction: str,
    ) -> dict:

        reverse_direction = self.client.get_reverse_direction(forward_direction)

        # Back-translate
        back_results = await self.client.translate_batch(
            translations, reverse_direction
        )

        results = []
        scores = []

        for orig, trans, back_r in zip(originals, translations, back_results):
            back_text = back_r.translated if back_r.success else ""
            score = self._similarity(orig, back_text)
            scores.append(score)

            results.append(QualityResult(
                original=orig,
                translated=trans,
                back_translated=back_text,
                score=score,
                flagged=score < self.FLAG_THRESHOLD,
            ))

        avg = sum(scores) / len(scores) if scores else 0.0
        flagged_count = sum(1 for r in results if r.flagged)

        return {
            "average_score": round(avg, 3),
            "flagged_count": flagged_count,
            "total_checked": len(results),
            "details": [
                {
                    "original": r.original[:80],
                    "score": round(r.score, 3),
                    "flagged": r.flagged,
                }
                for r in results
            ],
        }

    def _similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0

        a_words = set(a.lower().split())
        b_words = set(b.lower().split())

        if not a_words or not b_words:
            return 0.0

        intersection = a_words & b_words
        union = a_words | b_words

        jaccard = len(intersection) / len(union)

        a_chars = set(a.lower())
        b_chars = set(b.lower())
        char_sim = len(a_chars & b_chars) / len(a_chars | b_chars)

        return round(jaccard * 0.7 + char_sim * 0.3, 4)