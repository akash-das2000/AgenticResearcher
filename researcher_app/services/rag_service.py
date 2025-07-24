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
from django.conf import settings

from researcher_app.models import ExtractedContent

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TEXT_EMBED_URL  = os.environ["CLIP_TEXT_EMBED_URL"]
IMAGE_EMBED_URL = os.environ["CLIP_IMAGE_EMBED_URL"]
EMBED_HEADERS   = {"Content-Type": "application/json"}

GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
gemini_client   = genai.Client(api_key=GEMINI_API_KEY)

# ─── TOKENIZER & CHUNKING ─────────────────────────────────────────────────────
tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(txt, max_toks=500, overlap=100):
    toks = tokenizer.encode(txt)
    chunks = []
    for i in range(0, len(toks), max_toks - overlap):
        chunk = tokenizer.decode(toks[i : i + max_toks])
        chunks.append(chunk)
    return chunks

# ─── EMBEDDING HELPERS ────────────────────────────────────────────────────────
def embed_text_chunks(chunks):
    resp = requests.post(TEXT_EMBED_URL, json={"texts": chunks}, headers=EMBED_HEADERS)
    resp.raise_for_status()
    return resp.json()["embeddings"]

def embed_image(path_or_url):
    if path_or_url.startswith("http"):
        bts = requests.get(path_or_url).content
    else:
        with open(path_or_url, "rb") as f:
            bts = f.read()
    b64 = base64.b64encode(bts).decode()
    resp = requests.post(IMAGE_EMBED_URL, json={"images": [b64]}, headers=EMBED_HEADERS)
    resp.raise_for_status()
    return resp.json()["embeddings"][0]

# ─── RAG SERVICE ───────────────────────────────────────────────────────────────

class RAGService:
    def __init__(self, pdf_id):
        self.pdf_id    = pdf_id
        # path to persist the FAISS index + metadata
        self.index_path = os.path.join(settings.MEDIA_ROOT, f"indices/pdf_{pdf_id}.faiss")
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        ec = ExtractedContent.objects.get(pdf__id=pdf_id)
        self.full_text   = ec.text
        self.image_items = ec.images
        self.table_items = ec.tables

        self.index     = None
        self.metadatas = None

    def index_exists(self):
        return os.path.isfile(self.index_path)

    def build_index(self, persist=False):
        # 1) chunk & embed text
        text_chunks = chunk_text(self.full_text)
        text_vecs   = embed_text_chunks(text_chunks)

        # 2) prepare & embed tables
        table_chunks = []
        for tbl in self.table_items:
            df = pd.read_csv(tbl["url"])
            snippet = df.head(5).to_json(orient="records") if not df.empty else json.dumps({"columns": list(df.columns)})
            table_chunks.append({"content": f"Table p{tbl['page']}: {snippet}", **tbl})
        table_vecs = embed_text_chunks([t["content"] for t in table_chunks])

        # 3) embed images
        image_vecs = [embed_image(img["url"]) for img in self.image_items]

        # 4) assemble metadata
        metadatas = []
        for c in text_chunks:
            metadatas.append({"type":"text","content":c})
        for t in table_chunks:
            metadatas.append({"type":"table","content":t["content"],"page":t["page"],"url":t["url"]})
        for img in self.image_items:
            metadatas.append({"type":"image","page":img["page"],"url":img["url"]})
        self.metadatas = metadatas

        # 5) build FAISS index
        all_vecs = np.vstack([
            np.array(text_vecs,  dtype="float32"),
            np.array(table_vecs, dtype="float32"),
            np.array(image_vecs, dtype="float32")
        ])
        dim = all_vecs.shape[1]
        idx = faiss.IndexFlatL2(dim)
        idx.add(all_vecs)
        self.index = idx

        # 6) persist if requested
        if persist:
            faiss.write_index(idx, self.index_path)
            with open(self.index_path + ".meta", "w") as f:
                json.dump(self.metadatas, f)

    def _load_index(self):
        idx = faiss.read_index(self.index_path)
        with open(self.index_path + ".meta") as f:
            metas = json.load(f)
        self.index     = idx
        self.metadatas = metas

    def retrieve(self, query, k=3):
        # 1) lazy-load or (re)build index
        if self.index is None:
            if self.index_exists():
                self._load_index()
            else:
                self.build_index(persist=True)

        # 2) embed query
        qv, = embed_text_chunks([query])
        D, I = self.index.search(np.array([qv], dtype="float32"), k*5)

        # 3) collect top hits
        raw = []
        for dist, idx in zip(D[0], I[0]):
            md = self.metadatas[idx]
            raw.append({"distance": float(dist), **md})

        # (Optional) apply modality filtering… (omitted for brevity)
        return raw[:k]

    def ask_gemini(self, hits, question):
        parts = ["You are a precise multimodal research assistant.\n"]
        for h in hits:
            if h["type"] == "text":
                parts.append(f"[Text] {h['content']}\n")
            elif h["type"] == "table":
                df = pd.read_csv(h["url"])
                parts.append(f"Table (p{h['page']}):\n{df.head(5).to_markdown(index=False)}\n")
            elif h["type"] == "image":
                resp = requests.get(h["url"])
                parts.append(types.Part.from_bytes(data=resp.content, mime_type="image/png"))

        parts.append(f"QUESTION: {question}")
        resp = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=parts)
        return resp.text
