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




def extract_pdf(uploaded_file):
    """
    Extracts text, images, and tables from an uploaded PDF file.
    """
    import gc  # Add this for manual garbage collection

    # ✅ Save BytesIO to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    try:
        doc = fitz.open(tmp_path)

        # ✅ OCR Text (lower DPI to save memory)
        pages = convert_from_path(tmp_path, dpi=100)  # 👈 Lower DPI from 300 to 100
        pages_text = []
        for page in pages:
            text = pytesseract.image_to_string(page)
            pages_text.append(text)
            page.close()  # ✅ Free memory of each PIL image
        del pages  # ✅ Free list of PIL images
        gc.collect()  # ✅ Force GC to free RAM

        full_text = "\n\n".join(pages_text)

        # ✅ Clean Text
        cleaned_text = normalize_whitespace(
            fix_hyphenation(
                remove_headers_footers(pages_text)
            )
        )

        # ✅ Extract Images (keep only small images)
        images = []
        for page_num in range(doc.page_count):
            for img in doc[page_num].get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image = Image.open(io.BytesIO(image_bytes))
                if image.size[0] * image.size[1] > 2_000_000:  # 👈 Skip very large images
                    continue
                img_filename = f"page{page_num+1}_img.{image_ext}"
                img_path = os.path.join(IMAGES_DIR, img_filename)
                image.save(img_path)
                images.append({"page": page_num + 1, "path": img_path})
                image.close()  # ✅ Free image memory

        # ✅ Extract Tables
        tables = []
        with pdfplumber.open(tmp_path) as pdf:
            for i, page in enumerate(pdf.pages):
                for idx, table in enumerate(page.extract_tables() or []):
                    df = pd.DataFrame(table[1:], columns=table[0])
                    table_filename = f"table_{i+1}_{idx+1}.csv"
                    table_path = os.path.join(TABLES_DIR, table_filename)
                    df.to_csv(table_path, index=False)
                    tables.append({"page": i + 1, "path": table_path})
        del pdf  # ✅ Free pdfplumber object
        gc.collect()

        return {"text": cleaned_text, "images": images, "tables": tables}

    finally:
        # ✅ Clean up temporary file
        os.remove(tmp_path)







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
