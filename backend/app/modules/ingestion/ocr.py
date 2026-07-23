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
