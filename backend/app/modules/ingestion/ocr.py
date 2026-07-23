"""OCR providers (Doc §6.1) — pluggable, no cloud required.

RapidOcrProvider uses RapidOCR (ONNX, bundled models, fully offline) to read
scanned/image PDF pages; PyMuPDF rasterizes each page. NullOcrProvider is the
default (OCR off) so a scanned doc is flagged `needs_ocr` and degrades honestly
rather than silently producing garbage (Doc §12.4). AWS Textract can plug in
behind the same interface later for the hard table-heavy scans (TS-033)."""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class OcrProvider(Protocol):
    name: str

    def ocr_pdf(self, pdf_bytes: bytes) -> list[str]:
        """Return recognized text per page (index 0 = page 1)."""
        ...


class NullOcrProvider:
    name = "null"

    def ocr_pdf(self, pdf_bytes: bytes) -> list[str]:
        return []


class RapidOcrProvider:
    """Offline OCR via RapidOCR + PyMuPDF. Heavy deps are imported lazily and
    the engine is built once and reused."""

    name = "rapidocr"

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self._engine = None

    def _ocr(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def ocr_pdf(self, pdf_bytes: bytes) -> list[str]:
        import fitz  # PyMuPDF

        engine = self._ocr()
        pages: list[str] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                png = page.get_pixmap(dpi=self.dpi).tobytes("png")
                try:
                    result, _ = engine(png)
                except Exception:
                    logger.exception("OCR failed on a page")
                    result = None
                pages.append("\n".join(line[1] for line in result) if result else "")
        return pages


class RapidTableProvider:
    """Reconstruct a table from a SCANNED (image) BOQ page — fully offline, no
    cloud (replaces AWS Textract). Uses rapid-table's SLANet ONNX model +
    RapidOCR; the model is fetched once on first use, then runs offline.

    Defensive by design: any failure (incl. the one-time model fetch being
    unavailable) returns None so the caller degrades to `no_boq_table_found`
    rather than crashing. Not verifiable in the CI sandbox (model download
    blocked); works on a normal machine after the first-use download."""

    name = "rapidtable"

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self._ocr = None
        self._table = None

    def _engines(self):
        if self._ocr is None:
            from rapid_table import RapidTable
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
            self._table = RapidTable()
        return self._ocr, self._table

    def table_html(self, pdf_bytes: bytes) -> list[str]:
        """Return one HTML table string per page (empty string if none)."""
        import fitz
        import numpy as np

        try:
            import cv2
        except Exception:  # pragma: no cover - optional cv2
            logger.warning("rapidtable: opencv not available")
            return []
        try:
            ocr, table = self._engines()
        except Exception:
            logger.exception("rapidtable: engines/model unavailable")
            return []

        out: list[str] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                png = page.get_pixmap(dpi=self.dpi).tobytes("png")
                img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                try:
                    ocr_res, _ = ocr(img)
                    result = table(img, ocr_res)
                    html = getattr(result, "pred_html", None) or (
                        result[0] if isinstance(result, (tuple, list)) else str(result)
                    )
                except Exception:
                    logger.exception("rapidtable: recognition failed on a page")
                    html = ""
                out.append(html or "")
        return out
