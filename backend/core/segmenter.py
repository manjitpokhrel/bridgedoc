import re
from typing import List


class TrilingualSentenceSegmenter:

    ABBREVIATIONS_EN = {
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.",
        "vs.", "etc.", "i.e.", "e.g.", "No.", "Vol.", "pg.",
        "Fig.", "Jan.", "Feb.", "Mar.", "Apr.", "Jun.",
        "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.",
    }

    def __init__(self):
        self.devanagari_re = re.compile(r'[\u0900-\u097F]')
        self.speaker_pattern = re.compile(r'^[\u0900-\u097F\w]+\s*:')

    def segment(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        text = text.strip()

        deva_count = len(self.devanagari_re.findall(text))
        is_devanagari = deva_count > len(text) * 0.25

        if is_devanagari:
            return self._segment_devanagari(text)
        else:
            return self._segment_latin(text)

    def _segment_devanagari(self, text: str) -> List[str]:
        """
        Split Devanagari text into sentences.
        Handles dialogue format where mid-sentence ? or !
        should not cause a split.
        """
        # Split into lines first
        lines = text.split('\n')
        lines = [l.strip() for l in lines if l.strip()]

        # Detect if dialogue format
        speaker_count = sum(
            1 for l in lines
            if self.speaker_pattern.match(l)
        )
        is_dialogue = speaker_count > len(lines) * 0.4

        if is_dialogue:
            # Each line = one sentence, no mid-line splitting
            return [l for l in lines if l]

        # Normal sentence splitting on । ? !
        parts = re.split(r'([।?!]+)', text)
        sentences = []
        current = ""

        for part in parts:
            if re.match(r'^[।?!]+$', part):
                current += part
                s = current.strip()
                if s:
                    sentences.append(s)
                current = ""
            else:
                current += part

        if current.strip():
            sentences.append(current.strip())

        return [s for s in sentences if s]

    def _segment_latin(self, text: str) -> List[str]:
        """
        Split English text into sentences.
        Handles abbreviations to avoid false splits.
        """
        protected = text
        for abbr in self.ABBREVIATIONS_EN:
            placeholder = abbr.replace('.', '<!DOT!>')
            protected = protected.replace(abbr, placeholder)

        raw = re.split(
            r'(?<=[.!?])\s+(?=[A-Z\u0900-\u097F\"])',
            protected
        )

        sentences = []
        for s in raw:
            restored = s.replace('<!DOT!>', '.')
            s_clean = restored.strip()
            if s_clean:
                sentences.append(s_clean)

        return sentences if sentences else [text.strip()]

    def segment_units(self, units: list) -> list:
        for unit in units:
            unit["sentences"] = self.segment(unit.get("text", ""))
        return units