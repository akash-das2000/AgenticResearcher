# researcher_app/services/rag_service.py

import os
import io
import re
import json
import base64
import requests
import numpy as np
import faiss
import tiktoken
import pandas as pd

from google import genai
from google.genai import types

from researcher_app.models import ExtractedContent   # ← fixed import

# -----------------------------------------------------------------------------
# Configuration: read from ENV VARS
# -----------------------------------------------------------------------------
TEXT_EMBED_URL  = os.environ["CLIP_TEXT_EMBED_URL"]
IMAGE_EMBED_URL = os.environ["CLIP_IMAGE_EMBED_URL"]
EMBED_HEADERS   = {"Content-Type": "application/json"}

GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
gemini_client   = genai.Client(api_key=GEMINI_API_KEY)

# -----------------------------------------------------------------------------
# Tokenizer
# -----------------------------------------------------------------------------
tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(txt, max_toks=500, overlap=100):
    toks = tokenizer.encode(txt)
    chunks = []
    for i in range(0, len(toks), max_toks - overlap):
        chunk = tokenizer.decode(toks[i : i + max_toks])
        chunks.append(chunk)
    return chunks

# -----------------------------------------------------------------------------
# Embedding functions
# -----------------------------------------------------------------------------
def embed_text_chunks(chunks):
    resp = requests.post(TEXT_EMBED_URL, json={"texts": chunks}, headers=EMBED_HEADERS)
    resp.raise_for_status()
    return resp.json()["embeddings"]

def embed_image(path_or_url):
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        bts = requests.get(path_or_url).content
    else:
        with open(path_or_url, "rb") as f:
            bts = f.read()
    b64 = base64.b64encode(bts).decode()
    resp = requests.post(IMAGE_EMBED_URL, json={"images": [b64]}, headers=EMBED_HEADERS)
    resp.raise_for_status()
    return resp.json()["embeddings"][0]

# -----------------------------------------------------------------------------
# Modality detection & retrieval
# -----------------------------------------------------------------------------
def detect_modality(query):
    if m := re.search(r'\bfig(?:ure)?\.?\s*(\d+)\b', query, re.I):
        return "figure", int(m.group(1))
    if m := re.search(r'\btable\.?\s*(\d+)\b',   query, re.I):
        return "table", int(m.group(1))
    return "mixed", None

class RAGService:
    def __init__(self, pdf_id):
        ec = ExtractedContent.objects.get(uploaded_pdf_id=pdf_id)
        self.full_text    = ec.text
        self.image_items  = ec.images
        self.table_items  = ec.tables
        self.index        = None
        self.metadatas    = []

    def build_index(self):
        text_chunks = chunk_text(self.full_text)

        table_chunks = []
        for tbl in self.table_items:
            df = pd.read_csv(tbl["url"])
            snippet = df.head(5).to_json(orient="records") if not df.empty else json.dumps({"columns": list(df.columns)})
            table_chunks.append({"content": f"Table p{tbl['page']}: {snippet}", "page": tbl["page"], "url": tbl["url"]})

        text_vecs  = embed_text_chunks(text_chunks)
        table_vecs = embed_text_chunks([t["content"] for t in table_chunks])
        image_vecs = [embed_image(img["url"]) for img in self.image_items]

        self.metadatas = []
        for c in text_chunks:
            self.metadatas.append({"type":"text","content":c})
        for t in table_chunks:
            self.metadatas.append({"type":"table","content":t["content"],"page":t["page"],"url":t["url"]})
        for img in self.image_items:
            self.metadatas.append({"type":"image","page":img["page"],"url":img["url"]})

        all_vecs = np.vstack([np.array(text_vecs, dtype="float32"),
                              np.array(table_vecs, dtype="float32"),
                              np.array(image_vecs, dtype="float32")])
        dim = all_vecs.shape[1]
        idx = faiss.IndexFlatL2(dim)
        idx.add(all_vecs)
        self.index = idx

    def retrieve(self, query, k=3):
        mode, num = detect_modality(query)
        qv, = embed_text_chunks([query])
        D, I = self.index.search(np.array([qv],dtype="float32"), k*5)
        raw = [{"distance": float(D[0][i]), **self.metadatas[idx]} for i, idx in enumerate(I[0])]

        if mode == "figure":
            hits = [h for h in raw if h["type"]=="text" and re.search(fr'\bfig(?:ure)?\.?\s*{num}\b', h["content"], re.I)][:k]
            if 1 <= num <= len(self.image_items):
                img = self.image_items[num-1]
                hits.append({"type":"image","page":img["page"],"url":img["url"]})
            return hits

        if mode == "table":
            hits = [h for h in raw if h["type"]=="text" and re.search(fr'\btable\.?\s*{num}\b', h["content"], re.I)][:k]
            if 1 <= num <= len(self.table_items):
                tbl = self.table_items[num-1]
                hits.append({"type":"table","page":tbl["page"],"url":tbl["url"]})
            return hits

        return raw[:k]

    def ask_gemini(self, hits, question):
        contents = ["You are a precise multimodal research assistant.\n"]
        for h in hits:
            if h["type"] == "text":
                contents.append(f"[Text] {h['content']}\n")
            elif h["type"] == "table":
                df = pd.read_csv(h["url"])
                md = df.head(5).to_markdown(index=False)
                contents.append(f"Table (p{h['page']}):\n{md}\n")
            elif h["type"] == "image":
                resp = requests.get(h["url"])
                contents.append(types.Part.from_bytes(data=resp.content, mime_type="image/png"))

        contents.append(f"QUESTION: {question}")
        resp = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=contents)
        return resp.text
