import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.segmenter import TrilingualSentenceSegmenter

seg = TrilingualSentenceSegmenter()


def test_english_basic():
    text = "Hello world. How are you? I am fine."
    result = seg.segment(text)
    assert len(result) == 3


def test_nepali_purna_viram():
    text = "नमस्ते। तपाईंलाई कस्तो छ? म राम्रो छु।"
    result = seg.segment(text)
    assert len(result) >= 2


def test_empty_string():
    result = seg.segment("")
    assert result == []


def test_single_sentence():
    result = seg.segment("Hello world")
    assert len(result) == 1
    assert result[0] == "Hello world"


def test_abbreviation_not_split():
    text = "Dr. Smith went to the store. He bought milk."
    result = seg.segment(text)
    assert len(result) == 2


def test_mixed_script():
    text = "This is English. यो नेपाली हो। This is more English."
    result = seg.segment(text)
    assert len(result) >= 2