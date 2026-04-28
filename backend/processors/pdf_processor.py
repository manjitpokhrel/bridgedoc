import fitz  # PyMuPDF
import re
from pathlib import Path


class PDFProcessor:

    LINE_TOLERANCE = 3.0
    PARA_GAP_RATIO = 2.0
    WORD_GAP = 8.0
    TABLE_GAP = 80

    FONT_DIR = Path(__file__).resolve().parents[2] / "fonts"
    DEVANAGARI_FONT_PATH = FONT_DIR / "NotoSansDevanagari-Regular.ttf"
    DEVANAGARI_FONT_NAME = "NotoDeva"

    def extract(self, pdf_path: str) -> dict:
        try:
            if Path(pdf_path).stat().st_size == 0:
                return {
                    "can_translate": False,
                    "message": "PDF file is empty (0 bytes)."
                }
        except Exception:
            return {
                "can_translate": False,
                "message": "Unable to access PDF file."
            }

        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return {
                "can_translate": False,
                "message": "Could not open PDF file. It may be corrupted."
            }

        scan_info = self._detect_scan(doc)
        if not scan_info["can_translate"]:
            doc.close()
            return scan_info

        pages_data = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_dict = page.get_text(
                "dict", flags=fitz.TEXT_PRESERVE_WHITESPACE
            )
            spans = self._extract_spans(page_dict, page_num)
            logical_blocks = self._reconstruct_blocks(spans)

            pages_data.append({
                "page_num": page_num,
                "width": page.rect.width,
                "height": page.rect.height,
                "blocks": logical_blocks,
                "raw_spans": spans,
            })

        doc.close()

        units = []
        for page in pages_data:
            for block in page["blocks"]:
                if block["text"].strip():
                    units.append({
                        "text": block["text"],
                        "page_num": page["page_num"],
                        "bbox": block["bbox"],
                        "spans": block["spans"],
                        "is_table_cell": block.get("is_table_cell", False),
                        "translated": "",
                        "sentences": [],
                    })

        return {
            "can_translate": True,
            "warning": scan_info.get("warning"),
            "pages": pages_data,
            "translation_units": units,
            "source_path": pdf_path,
        }

    def _detect_scan(self, doc) -> dict:
        total = len(doc)
        image_pages = 0

        for page in doc:
            text = page.get_text().strip()
            if len(text) < 30:
                image_pages += 1

        if image_pages > total * 0.6:
            return {
                "can_translate": False,
                "message": (
                    "This PDF appears to be a scanned image. "
                    "Text cannot be extracted without OCR. "
                    "Please provide a digitally-created PDF."
                ),
            }

        warning = None
        if image_pages > 0:
            warning = (
                f"{image_pages} page(s) appear to be scanned images "
                f"and will be preserved as-is."
            )

        return {"can_translate": True, "warning": warning}

    def _extract_spans(self, page_dict: dict, page_num: int) -> list:
        spans = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        spans.append({
                            "text": text,
                            "bbox": tuple(span["bbox"]),
                            "font": span.get("font", ""),
                            "size": span.get("size", 12),
                            "color": span.get("color", 0),
                            "flags": span.get("flags", 0),
                            "page_num": page_num,
                        })
        return spans

    def _is_table_row(self, spans: list) -> bool:
        if len(spans) < 2:
            return False

        ys = [s["bbox"][1] for s in spans]
        if max(ys) - min(ys) > self.LINE_TOLERANCE:
            return False

        sorted_spans = sorted(spans, key=lambda s: s["bbox"][0])
        for i in range(1, len(sorted_spans)):
            prev_end = sorted_spans[i-1]["bbox"][2]
            curr_start = sorted_spans[i]["bbox"][0]
            gap = curr_start - prev_end
            if gap > self.TABLE_GAP:
                return True

        return False

    def _reconstruct_blocks(self, spans: list) -> list:
        if not spans:
            return []

        sorted_spans = self._reading_order(spans)
        lines = self._group_lines(sorted_spans)

        blocks = []
        para_lines = []

        for line in lines:
            if self._is_table_row(line):
                if para_lines:
                    paragraphs = self._group_paragraphs(para_lines)
                    for para_spans in paragraphs:
                        text = self._merge_to_text(para_spans)
                        if text:
                            blocks.append({
                                "text": text,
                                "bbox": self._union_bbox(para_spans),
                                "spans": para_spans,
                                "is_table_cell": False,
                            })
                    para_lines = []

                sorted_line = sorted(line, key=lambda s: s["bbox"][0])
                for span in sorted_line:
                    if span["text"].strip():
                        blocks.append({
                            "text": span["text"].strip(),
                            "bbox": tuple(span["bbox"]),
                            "spans": [span],
                            "is_table_cell": True,
                        })
            else:
                para_lines.append(line)

        if para_lines:
            paragraphs = self._group_paragraphs(para_lines)
            for para_spans in paragraphs:
                text = self._merge_to_text(para_spans)
                if text:
                    blocks.append({
                        "text": text,
                        "bbox": self._union_bbox(para_spans),
                        "spans": para_spans,
                        "is_table_cell": False,
                    })

        return blocks

    def _reading_order(self, spans: list) -> list:
        x_vals = [s["bbox"][0] for s in spans]
        if not x_vals:
            return spans

        sorted_x = sorted(set(round(x / 60) * 60 for x in x_vals))
        col_gap = (sorted_x[1] - sorted_x[0]) if len(sorted_x) > 1 else 0

        if col_gap > 120:
            mid = (sorted_x[0] + sorted_x[1]) / 2
            left = sorted(
                [s for s in spans if s["bbox"][0] < mid],
                key=lambda s: (s["bbox"][1], s["bbox"][0])
            )
            right = sorted(
                [s for s in spans if s["bbox"][0] >= mid],
                key=lambda s: (s["bbox"][1], s["bbox"][0])
            )
            return left + right

        return sorted(spans, key=lambda s: (
            round(s["bbox"][1] / 4) * 4,
            s["bbox"][0]
        ))

    def _group_lines(self, spans: list) -> list:
        if not spans:
            return []

        lines = []
        current_line = [spans[0]]
        current_y = spans[0]["bbox"][1]

        for span in spans[1:]:
            if abs(span["bbox"][1] - current_y) <= self.LINE_TOLERANCE:
                current_line.append(span)
            else:
                lines.append(sorted(
                    current_line, key=lambda s: s["bbox"][0]
                ))
                current_line = [span]
                current_y = span["bbox"][1]

        lines.append(sorted(current_line, key=lambda s: s["bbox"][0]))
        return lines

    def _group_paragraphs(self, lines: list) -> list:
        if not lines:
            return []

        heights = [
            lines[i][0]["bbox"][3] - lines[i][0]["bbox"][1]
            for i in range(len(lines)) if lines[i]
        ]
        avg_h = sum(heights) / len(heights) if heights else 12
        gap_threshold = avg_h * self.PARA_GAP_RATIO

        paragraphs = []
        current = list(lines[0])

        for i in range(1, len(lines)):
            prev_bottom = max(s["bbox"][3] for s in lines[i - 1])
            curr_top = min(s["bbox"][1] for s in lines[i])
            gap = curr_top - prev_bottom

            if gap > gap_threshold:
                paragraphs.append(current)
                current = list(lines[i])
            else:
                current.extend(lines[i])

        paragraphs.append(current)
        return paragraphs

    def _merge_to_text(self, spans: list) -> str:
        if not spans:
            return ""

        sorted_s = sorted(spans, key=lambda s: (
            round(s["bbox"][1] / 4) * 4, s["bbox"][0]
        ))

        result = ""
        prev = None

        for span in sorted_s:
            if prev is None:
                result = span["text"]
            else:
                prev_bottom = prev["bbox"][1]
                curr_top = span["bbox"][1]
                line_changed = abs(curr_top - prev_bottom) > self.LINE_TOLERANCE
                gap = span["bbox"][0] - prev["bbox"][2]

                if line_changed:
                    if not result.endswith(" "):
                        result += " "
                    result += span["text"].lstrip()
                elif gap > self.WORD_GAP:
                    if not result.endswith(" ") and not span["text"].startswith(" "):
                        result += " "
                    result += span["text"]
                else:
                    result += span["text"]
            prev = span

        return result.strip()

    def _union_bbox(self, spans: list) -> tuple:
        return (
            min(s["bbox"][0] for s in spans),
            min(s["bbox"][1] for s in spans),
            max(s["bbox"][2] for s in spans),
            max(s["bbox"][3] for s in spans),
        )

    def _get_fontname_for_direction(self, page, direction: str) -> str:
        """
        Use Devanagari font when target is Nepali or Tamang.
        Use helv when target is English.
        """
        target = direction.split("→")[-1].strip().lower()
        is_devanagari_target = target in ["ne", "tamang"]

        if is_devanagari_target and self.DEVANAGARI_FONT_PATH.exists():
            try:
                page.insert_font(
                    fontname=self.DEVANAGARI_FONT_NAME,
                    fontfile=str(self.DEVANAGARI_FONT_PATH)
                )
                return self.DEVANAGARI_FONT_NAME
            except Exception:
                return "helv"
        return "helv"

    def rebuild(self, doc_data: dict, output_path: str, direction: str = "en→ne") -> dict:
        source_path = doc_data["source_path"]
        units = doc_data["translation_units"]
        doc = fitz.open(source_path)

        page_groups = {}
        for unit in units:
            p_num = unit["page_num"]
            if p_num not in page_groups:
                page_groups[p_num] = []
            page_groups[p_num].append(unit)

        for page_num, page_units in page_groups.items():
            page = doc[page_num]
            page_height = page.rect.height

            sorted_units = sorted(page_units, key=lambda u: u["bbox"][1])

            max_bottoms = {}
            for i, unit in enumerate(sorted_units):
                if i < len(sorted_units) - 1:
                    next_top = sorted_units[i + 1]["bbox"][1]
                    max_bottoms[id(unit)] = next_top - 2
                else:
                    max_bottoms[id(unit)] = page_height - 10

            # Register font for this page
            fontname = self._get_fontname_for_direction(page, direction)

            for unit in sorted_units:
                try:
                    translated = unit.get("translated", "").strip()
                    original = unit.get("text", "").strip()

                    if not translated or translated == original:
                        continue

                    if self._should_skip_translation(original):
                        continue

                    rect = fitz.Rect(unit["bbox"])
                    if rect.width < 5 or rect.height < 5:
                        continue

                    if self._overlaps_image(page, rect):
                        continue

                    fontsize = unit["spans"][0]["size"] if unit["spans"] else 9

                    color = (0, 0, 0)
                    if unit["spans"]:
                        color = self._int_to_rgb(unit["spans"][0]["color"])
                        if all(c > 0.85 for c in color):
                            color = (0, 0, 0)

                    is_table_cell = unit.get("is_table_cell", False)
                    is_single_line = rect.height <= 15

                    if is_table_cell or is_single_line:
                        # Try fitting — if not, keep original
                        fit_font = None
                        for fs in [fontsize, fontsize*0.85,
                                   fontsize*0.75, 7.0, 6.5, 6.0]:
                            rc = page.insert_textbox(
                                rect, translated,
                                fontname=fontname,
                                fontsize=fs,
                                color=(1, 1, 1),
                                align=0,
                            )
                            if rc >= 0:
                                fit_font = fs
                                break

                        if fit_font is None:
                            continue

                        page.add_redact_annot(
                            fitz.Rect(rect.x0-1, rect.y0-1,
                                      rect.x1+1, rect.y1+1),
                            fill=(1, 1, 1)
                        )
                        page.apply_redactions()
                        fontname = self._get_fontname_for_direction(
                            page, direction
                        )

                        page.insert_textbox(
                            rect, translated,
                            fontname=fontname,
                            fontsize=fit_font,
                            color=color,
                            align=0,
                        )

                    else:
                        max_bottom = max_bottoms.get(
                            id(unit), page_height - 10
                        )
                        best_rect = None
                        best_fontsize = fontsize

                        for expand in [0, 10, 20, 35, 50]:
                            new_bottom = min(
                                rect.y1 + expand, max_bottom
                            )
                            if new_bottom <= rect.y1:
                                break

                            trial_rect = fitz.Rect(
                                rect.x0, rect.y0,
                                rect.x1, new_bottom
                            )
                            rc = page.insert_textbox(
                                trial_rect, translated,
                                fontname=fontname,
                                fontsize=fontsize,
                                color=(1, 1, 1),
                                align=0,
                            )
                            if rc >= 0:
                                best_rect = trial_rect
                                best_fontsize = fontsize
                                break

                        if best_rect is None:
                            trial_rect = fitz.Rect(
                                rect.x0, rect.y0,
                                rect.x1, max_bottom
                            )
                            for fs in [fontsize*0.85, fontsize*0.75,
                                       8.0, 7.0, 6.5, 6.0]:
                                rc = page.insert_textbox(
                                    trial_rect, translated,
                                    fontname=fontname,
                                    fontsize=fs,
                                    color=(1, 1, 1),
                                    align=0,
                                )
                                if rc >= 0:
                                    best_rect = trial_rect
                                    best_fontsize = fs
                                    break

                        if best_rect is None:
                            continue

                        page.add_redact_annot(
                            fitz.Rect(rect.x0-1, rect.y0-1,
                                      rect.x1+1, rect.y1+1),
                            fill=(1, 1, 1)
                        )
                        page.apply_redactions()
                        fontname = self._get_fontname_for_direction(
                            page, direction
                        )

                        page.insert_textbox(
                            best_rect, translated,
                            fontname=fontname,
                            fontsize=best_fontsize,
                            color=color,
                            align=0,
                        )

                except Exception as e:
                    print(f"Unit failed: {e}")
                    continue

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()

        return {
            "translated": len(units),
            "failed": 0,
            "total_sentences": len(units),
        }

    def _should_skip_translation(self, text: str) -> bool:
        text = text.strip()
        if re.match(r'https?://', text):
            return True
        if re.match(r'^[\d,.\s]+$', text):
            return True
        if re.match(
            r'^(January|February|March|April|May|June|July|August|'
            r'September|October|November|December|'
            r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
            text
        ):
            return True
        if len(text.strip()) <= 1:
            return True
        return False

    def _has_devanagari(self, text: str) -> bool:
        return any('\u0900' <= c <= '\u097F' for c in text)

    def _overlaps_image(self, page, rect: fitz.Rect) -> bool:
        try:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 1:
                    img_rect = fitz.Rect(block["bbox"])
                    intersection = rect & img_rect
                    if not intersection.is_empty:
                        overlap_area = (intersection.width *
                                        intersection.height)
                        rect_area = rect.width * rect.height
                        if rect_area > 0 and overlap_area / rect_area > 0.3:
                            return True
        except Exception:
            pass
        return False

    def _int_to_rgb(self, color_int: int) -> tuple:
        r = ((color_int >> 16) & 0xFF) / 255
        g = ((color_int >> 8) & 0xFF) / 255
        b = (color_int & 0xFF) / 255
        return (r, g, b)