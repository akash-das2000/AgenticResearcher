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




def extract_pdf(file_or_path):
    """
    Extracts text, images, and tables from a PDF file.

    Supports both:
    - file_or_path = str (path to PDF file)
    - file_or_path = file-like object (BytesIO, UploadedFile)
    """
    import traceback

    cleanup_temp = False

    # ✅ Detect if file_or_path is a path or file-like object
    if isinstance(file_or_path, str):
        pdf_source = file_or_path
    elif hasattr(file_or_path, "read"):  # file-like object
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(file_or_path.read())
                pdf_source = tmp_file.name
            cleanup_temp = True
        except Exception as e:
            print(f"❌ Failed to create temp file: {e}")
            traceback.print_exc()
            raise
    else:
        raise ValueError("Invalid file_or_path: expected path or file-like object")

    print(f"DEBUG: extract_pdf opening {pdf_source}")

    try:
        # ✅ Process with fitz (PyMuPDF)
        doc = fitz.open(pdf_source)
        print(f"DEBUG: PDF loaded successfully with {doc.page_count} pages")

        # ✅ OCR Text (low DPI to save memory)
        pages = convert_from_path(pdf_source, dpi=72)
        pages_text = []
        for page_num, page in enumerate(pages, 1):
            text = pytesseract.image_to_string(page)
            pages_text.append(text)
            print(f"DEBUG: OCR text extracted for page {page_num}")

        full_text = "\n\n".join(pages_text)

        # ✅ Clean Text
        cleaned_text = normalize_whitespace(
            fix_hyphenation(remove_headers_footers(pages_text))
        )
        print(f"DEBUG: Cleaned text length = {len(cleaned_text)}")

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
        print(f"DEBUG: Total images extracted = {len(images)}")

        # ✅ Extract Tables
        tables = []
        with pdfplumber.open(pdf_source) as pdf:
            for i, page in enumerate(pdf.pages):
                for idx, table in enumerate(page.extract_tables() or []):
                    df = pd.DataFrame(table[1:], columns=table[0])
                    table_filename = f"table_{i+1}_{idx+1}.csv"
                    table_path = os.path.join(TABLES_DIR, table_filename)
                    df.to_csv(table_path, index=False)
                    tables.append({"page": i + 1, "path": table_path})
        print(f"DEBUG: Total tables extracted = {len(tables)}")

        return {"text": cleaned_text, "images": images, "tables": tables}

    except Exception as e:
        print(f"❌ extract_pdf failed: {e}")
        traceback.print_exc()
        return {"text": "", "images": [], "tables": []}

    finally:
        if cleanup_temp and os.path.exists(pdf_source):
            try:
                os.remove(pdf_source)
                print(f"DEBUG: Temp file {pdf_source} deleted")
            except Exception as cleanup_err:
                print(f"⚠️ Failed to delete temp file: {cleanup_err}")







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
