import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from processors.pdf_processor import PDFProcessor


def test_int_to_rgb():
    proc = PDFProcessor()
    r, g, b = proc._int_to_rgb(0xFF0000)
    assert abs(r - 1.0) < 0.01
    assert abs(g - 0.0) < 0.01


def test_union_bbox():
    proc = PDFProcessor()
    spans = [
        {"bbox": (10, 20, 100, 40)},
        {"bbox": (50, 10, 200, 35)},
    ]
    bbox = proc._union_bbox(spans)
    assert bbox == (10, 10, 200, 40)


def test_adjust_font_size_no_change():
    proc = PDFProcessor()
    import fitz
    rect = fitz.Rect(0, 0, 200, 20)
    size = proc._adjust_font_size("Hello", "Hello", rect, 12.0)
    assert size == 12.0


def test_adjust_font_size_shrink():
    proc = PDFProcessor()
    import fitz
    rect = fitz.Rect(0, 0, 100, 20)
    # Translated is much longer
    size = proc._adjust_font_size("Hi", "Hello world how are you doing today", rect, 12.0)
    assert size < 12.0