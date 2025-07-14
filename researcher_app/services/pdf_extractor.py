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

# ✅ Output directories
SAVE_DIR = os.path.join(settings.MEDIA_ROOT, "outputs")
IMAGES_DIR = os.path.join(SAVE_DIR, "extracted_images")
TABLES_DIR = os.path.join(SAVE_DIR, "extracted_tables")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)




def extract_pdf(pdf_path):
    """
    Extracts text, images, and tables from PDF.

    Args:
        pdf_path (str): Absolute path to PDF file.

    Returns:
        dict: {"text": str, "images": [paths], "tables": [paths]}
    """
    print(f"DEBUG: Starting PDF extraction for {pdf_path}")
    try:
        # ✅ Ensure path is string
        pdf_path = str(pdf_path)

        # ✅ Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)

        # ✅ OCR Text
        pages_text = []
        try:
            pages = convert_from_path(pdf_path)
        except Exception as e:
            print(f"WARNING: convert_from_path fallback failed: {e}")
            with open(pdf_path, "rb") as f:
                pages = convert_from_path(f)

        for page in pages:
            text = pytesseract.image_to_string(page)
            pages_text.append(text)
        full_text = "\n\n".join(pages_text)

        # ✅ Clean Text
        cleaned_text = normalize_whitespace(
            fix_hyphenation(
                remove_headers_footers(pages_text)
            )
        )

        # ✅ Extract Images
        images = []
        for page_num in range(doc.page_count):
            for img in doc[page_num].get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image = Image.open(io.BytesIO(image_bytes))
                img_filename = f"page{page_num+1}_img.{image_ext}"
                img_path = os.path.join(IMAGES_DIR, img_filename)
                image.save(img_path)
                images.append({"page": page_num + 1, "path": img_path})

        # ✅ Extract Tables
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                for idx, table in enumerate(page.extract_tables() or []):
                    df = pd.DataFrame(table[1:], columns=table[0])
                    table_filename = f"table_{i+1}_{idx+1}.csv"
                    table_path = os.path.join(TABLES_DIR, table_filename)
                    df.to_csv(table_path, index=False)
                    tables.append({"page": i + 1, "path": table_path})

        return {"text": cleaned_text, "images": images, "tables": tables}

    except Exception as e:
        print(f"ERROR parsing PDF: {e}")
        raise e






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
