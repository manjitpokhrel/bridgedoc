import pandas as pd
import re
from datetime import datetime
from pathlib import Path


class CSVProcessor:

    SKIP_PATTERNS = [
        r'^\d+\.?\d*$',                      # pure numbers
        r'^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}',  # dates with separators
        r'^[A-Z]{1,4}\d+$',                  # codes like NP001, ABC123
        r'^\+?\d[\d\s\-()]{6,}$',            # phone numbers
        r'^[\w.+\-]+@[\w\-]+\.[a-z]{2,}$',  # emails
        r'^https?://',                        # URLs
        r'^\s*$',                             # empty/whitespace
        r'^[०-९]+$',                         # Nepali numerals only
    ]

    DATE_FORMATS = [
        '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
        '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y',
    ]

    def extract(self, file_path: str) -> dict:
        delimiter = '\t' if file_path.endswith('.tsv') else ','

        try:
            if Path(file_path).stat().st_size == 0:
                return {
                    "can_translate": False,
                    "message": "CSV/TSV file is empty.",
                    "translation_units": [],
                    "dataframe": None,
                    "column_types": {},
                    "delimiter": delimiter,
                    "source_path": file_path,
                }
        except Exception:
            return {
                "can_translate": False,
                "message": "Unable to access file.",
                "translation_units": [],
                "dataframe": None,
                "column_types": {},
                "delimiter": delimiter,
                "source_path": file_path,
            }

        try:
            df = pd.read_csv(
                file_path,
                delimiter=delimiter,
                dtype=str,
                keep_default_na=False,
                on_bad_lines='skip',
            )
        except Exception:
            return {
                "can_translate": False,
                "message": "Failed to parse CSV/TSV. File may be malformed.",
                "translation_units": [],
                "dataframe": None,
                "column_types": {},
                "delimiter": delimiter,
                "source_path": file_path,
            }

        if df.empty:
            return {
                "can_translate": False,
                "message": "CSV/TSV file contains no readable data.",
                "translation_units": [],
                "dataframe": df,
                "column_types": {},
                "delimiter": delimiter,
                "source_path": file_path,
            }

        column_types = self._analyze_columns(df)
        units = []

        # Translate headers
        for col in df.columns:
            if not self._should_skip(col):
                units.append({
                    "text": col,
                    "location": {"type": "header", "col": col},
                    "translated": "",
                    "sentences": [],
                })

        # Translate cells
        for col in df.columns:
            col_type = column_types.get(col, "translate")
            if col_type == "skip":
                continue

            for idx, val in df[col].items():
                val_str = str(val).strip()
                if not val_str:
                    continue
                if self._should_skip(val_str):
                    continue

                units.append({
                    "text": val_str,
                    "location": {"type": "cell", "col": col, "idx": idx},
                    "translated": "",
                    "sentences": [],
                })

        if not units:
            return {
                "can_translate": False,
                "message": "No translatable text found in this CSV/TSV.",
                "translation_units": [],
                "dataframe": df,
                "column_types": column_types,
                "delimiter": delimiter,
                "source_path": file_path,
            }

        return {
            "can_translate": True,
            "source_path": file_path,
            "translation_units": units,
            "dataframe": df,
            "column_types": column_types,
            "delimiter": delimiter,
        }

    def rebuild(
        self,
        doc_data: dict,
        translation_map: dict,
        output_path: str,
    ) -> dict:
        df = doc_data["dataframe"].copy()
        delimiter = doc_data["delimiter"]
        units = doc_data["translation_units"]
        column_types = doc_data["column_types"]

        # Rename translated headers
        rename_map = {}
        for unit in units:
            if unit["location"]["type"] == "header":
                orig_col = unit["location"]["col"]
                translated = translation_map.get(unit["text"], unit["text"])
                if translated and translated != unit["text"]:
                    rename_map[orig_col] = translated

        df = df.rename(columns=rename_map)

        # Apply translated cells
        for unit in units:
            if unit["location"]["type"] == "cell":
                orig_col = unit["location"]["col"]
                new_col = rename_map.get(orig_col, orig_col)
                idx = unit["location"]["idx"]
                translated = translation_map.get(unit["text"], unit["text"])
                if new_col in df.columns:
                    df.at[idx, new_col] = translated

        df.to_csv(
            output_path,
            sep=delimiter,
            index=False,
            encoding="utf-8-sig"
        )

        translated = sum(
            1 for u in units
            if translation_map.get(u["text"]) not in (None, u["text"])
        )
        skipped = [
            col for col, t in column_types.items() if t == "skip"
        ]

        return {
            "translated": translated,
            "failed": 0,
            "total_sentences": len(units),
            "skipped_columns": skipped,
        }

    def _analyze_columns(self, df: pd.DataFrame) -> dict:
        result = {}
        for col in df.columns:
            vals = [str(v).strip() for v in df[col] if str(v).strip()]
            if not vals:
                result[col] = "skip"
                continue
            skip_count = sum(1 for v in vals if self._should_skip(v))
            ratio = skip_count / len(vals)
            if ratio > 0.85:
                result[col] = "skip"
            elif ratio > 0.4:
                result[col] = "partial"
            else:
                result[col] = "translate"
        return result

    def _should_skip(self, value: str) -> bool:
        value = value.strip()
        if not value:
            return True
        for pattern in self.SKIP_PATTERNS:
            if re.match(pattern, value, re.IGNORECASE):
                return True
        for fmt in self.DATE_FORMATS:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                pass
        return False