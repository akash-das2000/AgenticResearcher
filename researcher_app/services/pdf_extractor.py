# services/pdf_extractor.py

import os
import io
import tempfile
import logging
from collections import Counter

import fitz                       # PyMuPDF
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import pandas as pd
import re

from django.conf import settings

# Output directories under MEDIA_ROOT/outputs/
SAVE_DIR    = os.path.join(settings.MEDIA_ROOT, "outputs")
IMAGES_DIR  = os.path.join(SAVE_DIR, "extracted_images")
TABLES_DIR  = os.path.join(SAVE_DIR, "extracted_tables")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

logger = logging.getLogger(__name__)


def extract_pdf(file_or_path) -> dict:
    """
    Extract text (with MuPDF/pdfplumber/OCR fallback), images, and tables from a PDF.

    Args:
        file_or_path: path to PDF (str) or file-like object with .read()

    Returns:
        {
            "text": str,      # the full extracted & cleaned text
            "images": [       # list of {"page": int, "path": str}
                {"page": 1, "path": "..."},
                ...
            ],
            "tables": [       # list of {"page": int, "path": str}
                {"page": 2, "path": "..."},
                ...
            ]
        }
    """
    # 1. Prepare a disk path for the PDF
    cleanup_temp = False
    if isinstance(file_or_path, str):
        pdf_path = file_or_path
    elif hasattr(file_or_path, "read"):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(file_or_path.read())
        tmp.close()
        pdf_path = tmp.name
        cleanup_temp = True
    else:
        raise ValueError("extract_pdf: expected file path or file-like object")

    text_pages = []
    images = []
    tables = []

    try:
        # 2. Open with PyMuPDF
        try:
            doc = fitz.open(pdf_path)
            page_count = doc.page_count
            logger.debug(f"Opened PDF with {page_count} pages via PyMuPDF")
        except Exception:
            logger.exception("Failed to open PDF with PyMuPDF")
            page_count = 0

        # 3. Extract text per page
        for i in range(page_count):
            page_num = i + 1
            page_text = ""

            # 3.1) MuPDF text
            try:
                page = doc.load_page(i)
                page_text = page.get_text().strip()
                logger.debug(f"Page {page_num}: MuPDF extracted {len(page_text)} chars")
            except Exception:
                logger.exception(f"Page {page_num}: MuPDF text extraction failed")

            # 3.2) pdfplumber fallback
            if not page_text:
                try:
                    with pdfplumber.open(pdf_path) as pl:
                        pl_page = pl.pages[i]
                        page_text = (pl_page.extract_text() or "").strip()
                    logger.debug(f"Page {page_num}: pdfplumber extracted {len(page_text)} chars")
                except Exception:
                    logger.exception(f"Page {page_num}: pdfplumber extraction failed")

            # 3.3) OCR fallback at 300 DPI
            if not page_text:
                try:
                    img = convert_from_path(
                        pdf_path, dpi=300,
                        first_page=page_num, last_page=page_num
                    )[0]
                    page_text = pytesseract.image_to_string(img).strip()
                    logger.debug(f"Page {page_num}: OCR extracted {len(page_text)} chars")
                except Exception:
                    logger.exception(f"Page {page_num}: OCR extraction failed")

            text_pages.append(page_text or f"[Page {page_num}: no text]")

        # 4. Clean the full text
        #    remove common headers/footers, fix hyphens, normalize whitespace
        cleaned_str  = remove_headers_footers(text_pages)
        cleaned_str  = fix_hyphenation(cleaned_str)
        cleaned_text = normalize_whitespace(cleaned_str)
        logger.debug(f"Cleaned text length = {len(cleaned_text)}")

        # 5. Extract images (PyMuPDF)
        for i in range(page_count):
            page_num = i + 1
            try:
                for img_index, img in enumerate(doc[i].get_images(full=True), start=1):
                    xref       = img[0]
                    base       = doc.extract_image(xref)
                    img_bytes  = base["image"]
                    ext        = base["ext"]
                    pil_img    = Image.open(io.BytesIO(img_bytes))
                    filename   = f"page{page_num}_img{img_index}.{ext}"
                    path       = os.path.join(IMAGES_DIR, filename)
                    pil_img.save(path)
                    images.append({"page": page_num, "path": path})
                logger.debug(f"Page {page_num}: total images so far = {len(images)}")
            except Exception:
                logger.exception(f"Page {page_num}: image extraction failed")

        # 6. Extract tables (pdfplumber)
        try:
            with pdfplumber.open(pdf_path) as pl:
                for i, pl_page in enumerate(pl.pages):
                    for tbl_idx, table in enumerate(pl_page.extract_tables() or [], start=1):
                        df = pd.DataFrame(table[1:], columns=table[0])
                        filename = f"table_p{i+1}_{tbl_idx}.csv"
                        path     = os.path.join(TABLES_DIR, filename)
                        df.to_csv(path, index=False)
                        tables.append({"page": i + 1, "path": path})
                logger.debug(f"Extracted {len(tables)} tables in total")
        except Exception:
            logger.exception("Table extraction via pdfplumber failed")

        return {
            "text":   cleaned_text,
            "images": images,
            "tables": tables,
        }

    finally:
        if cleanup_temp and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.debug(f"Deleted temp PDF {pdf_path}")
            except Exception:
                logger.exception(f"Failed to delete temp PDF {pdf_path}")


# ─────── Helpers ──────────────────────────────────────────────────────────────

def remove_headers_footers(pages, threshold=0.5):
    """
    Removes lines common to most pages (headers/footers).
    """
    counter = Counter()
    for page in pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        counter.update(lines)
    common = {ln for ln, cnt in counter.items() if cnt / len(pages) >= threshold}
    cleaned_pages = []
    for page in pages:
        filtered = [ln for ln in page.splitlines() if ln.strip() not in common]
        cleaned_pages.append("\n".join(filtered))
    return "\n\n".join(cleaned_pages)


def fix_hyphenation(text):
    """
    Joins hyphenated words split across lines.
    """
    return re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)


def normalize_whitespace(text):
    """
    Collapse all whitespace to single spaces and trim.
    """
    return re.sub(r'\s+', ' ', text).strip()
