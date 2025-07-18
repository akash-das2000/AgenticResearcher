# services/pdf_extractor.py

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import pandas as pd
import re
import io
import os
import tempfile
from collections import Counter
from django.conf import settings
import logging

# ✅ Output directories
SAVE_DIR = os.path.join(settings.MEDIA_ROOT, "outputs")
IMAGES_DIR = os.path.join(SAVE_DIR, "extracted_images")
TABLES_DIR = os.path.join(SAVE_DIR, "extracted_tables")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)


logger = logging.getLogger(__name__)

def extract_pdf(
    file_or_path,
    images_dir: str = "extracted_images",
    tables_dir: str = "extracted_tables"
) -> dict:
    """
    Extract text (with MuPDF/pdfplumber/OCR fallback), images, and tables from a PDF.

    Args:
        file_or_path: path to PDF (str) or file-like object with .read()
        images_dir: folder where extracted images will be saved
        tables_dir: folder where extracted tables (CSV) will be saved

    Returns:
        {
            "text": str,            # the full extracted & cleaned text
            "images": [             # list of {"page": int, "path": str}
                {"page": 1, "path": "..."},
                ...
            ],
            "tables": [             # list of {"page": int, "path": str}
                {"page": 2, "path": "..."},
                ...
            ]
        }
    """
    # 1. Prepare source PDF on disk
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

    # 2. Ensure output dirs exist
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(tables_dir, exist_ok=True)

    text_pages = []
    images = []
    tables = []

    try:
        # Open with PyMuPDF
        try:
            doc = fitz.open(pdf_path)
            page_count = doc.page_count
            logger.debug(f"Opened PDF with {page_count} pages via PyMuPDF")
        except Exception:
            logger.exception("Failed to open PDF with PyMuPDF")
            page_count = 0

        # Extract text per page
        for i in range(page_count):
            page_num = i + 1
            page_text = ""

            # --- 1) MuPDF text
            try:
                page = doc.load_page(i)
                page_text = page.get_text().strip()
                logger.debug(f"Page {page_num}: MuPDF extracted {len(page_text)} chars")
            except Exception:
                logger.exception(f"Page {page_num}: MuPDF text extraction failed")

            # --- 2) pdfplumber fallback
            if not page_text:
                try:
                    with pdfplumber.open(pdf_path) as plumber_pdf:
                        pl_page = plumber_pdf.pages[i]
                        page_text = (pl_page.extract_text() or "").strip()
                    logger.debug(f"Page {page_num}: pdfplumber extracted {len(page_text)} chars")
                except Exception:
                    logger.exception(f"Page {page_num}: pdfplumber extraction failed")

            # --- 3) OCR fallback
            if not page_text:
                try:
                    pil_imgs = convert_from_path(pdf_path, dpi=150,
                                                first_page=page_num,
                                                last_page=page_num)
                    ocr_text = pytesseract.image_to_string(pil_imgs[0])
                    page_text = ocr_text.strip()
                    logger.debug(f"Page {page_num}: OCR extracted {len(page_text)} chars")
                except Exception:
                    logger.exception(f"Page {page_num}: OCR extraction failed")

            # Clean and store
            cleaned = normalize_whitespace(
                fix_hyphenation(remove_headers_footers(page_text))
            )
            text_pages.append(cleaned or f"[Page {page_num}: no text]")

        # 3. Extract images
        for i in range(page_count):
            page_num = i + 1
            try:
                for img_index, img in enumerate(doc[i].get_images(full=True), start=1):
                    xref = img[0]
                    base = doc.extract_image(xref)
                    img_bytes = base["image"]
                    ext = base["ext"]
                    img_obj = Image.open(io.BytesIO(img_bytes))
                    filename = f"page{page_num}_img{img_index}.{ext}"
                    path = os.path.join(images_dir, filename)
                    img_obj.save(path)
                    images.append({"page": page_num, "path": path})
                logger.debug(f"Page {page_num}: extracted {len(images)} total images so far")
            except Exception:
                logger.exception(f"Page {page_num}: image extraction failed")

        # 4. Extract tables
        try:
            with pdfplumber.open(pdf_path) as plumber_pdf:
                for i, pl_page in enumerate(plumber_pdf.pages):
                    for tbl_idx, table in enumerate(pl_page.extract_tables() or [], start=1):
                        df = pd.DataFrame(table[1:], columns=table[0])
                        filename = f"table_p{i+1}_{tbl_idx}.csv"
                        path = os.path.join(tables_dir, filename)
                        df.to_csv(path, index=False)
                        tables.append({"page": i + 1, "path": path})
                logger.debug(f"Extracted {len(tables)} tables in total")
        except Exception:
            logger.exception("Table extraction via pdfplumber failed")

        return {
            "text": "\n\n".join(text_pages),
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







# 🔥 Helpers
def remove_headers_footers(pages, threshold=0.5):
    """
    Removes common header/footer lines appearing on most pages.
    """
    counter = Counter()
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        counter.update(lines)
    common = {line for line, count in counter.items() if count / len(pages) >= threshold}
    return "\n".join(
        "\n".join(line for line in page.splitlines() if line.strip() not in common)
        for page in pages
    )

def fix_hyphenation(text):
    """
    Fixes hyphenated words split across lines.
    """
    return re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

def normalize_whitespace(text):
    """
    Normalizes whitespace to single spaces and trims text.
    """
    return re.sub(r'\s+', ' ', text).strip()
