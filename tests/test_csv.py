import sys, os
import pandas as pd
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from processors.csv_processor import CSVProcessor

proc = CSVProcessor()


def test_should_skip_number():
    assert proc._should_skip("12345") is True
    assert proc._should_skip("3.14") is True


def test_should_skip_email():
    assert proc._should_skip("test@example.com") is True


def test_should_skip_url():
    assert proc._should_skip("https://google.com") is True


def test_should_not_skip_text():
    assert proc._should_skip("Hello world") is False
    assert proc._should_skip("नमस्ते") is False


def test_column_analysis():
    df = pd.DataFrame({
        "name": ["Ram", "Sita", "Hari"],
        "age": ["25", "30", "22"],
        "email": ["a@b.com", "c@d.com", "e@f.com"],
    })
    types = proc._analyze_columns(df)
    assert types["age"] == "skip"
    assert types["email"] == "skip"
    assert types["name"] == "translate"


def test_extract_csv():
    with tempfile.NamedTemporaryFile(
        suffix=".csv", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("name,age,city\nRam,25,Kathmandu\nSita,30,Pokhara\n")
        path = f.name

    result = proc.extract(path)
    assert "translation_units" in result
    texts = [u["text"] for u in result["translation_units"]]
    assert "Kathmandu" in texts
    assert "25" not in texts  # number skipped
    os.unlink(path)