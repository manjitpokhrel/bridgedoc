from pathlib import Path
import fitz

FONTS_DIR = Path(__file__).parent.parent.parent / "fonts"


def register_devanagari_font():
    """
    Register Devanagari font with PyMuPDF if available.
    Falls back to built-in helvetica if not.
    """
    font_path = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"
    if font_path.exists():
        return str(font_path)
    return None


def has_devanagari(text: str) -> bool:
    return any('\u0900' <= c <= '\u097F' for c in text)