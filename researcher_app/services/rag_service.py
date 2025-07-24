# researcher_app/services/rag_service.py

import os
import json
import re
import base64
import requests
import numpy as np
import pandas as pd
import faiss
import tiktoken

from django.conf import settings
from researcher_app.models import ExtractedContent
from google import genai
from google.genai import types

# ─── CONFIG & CLIENTS ─────────────────────────────────────────────────────────
TEXT_EMBED_URL  = os.environ["CLIP_TEXT_EMBED_URL"]
IMAGE_EMBED_URL = os.environ["CLIP_IMAGE_EMBED_URL"]
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]

EMBED_HEADERS = {"Content-Type": "application/json"}
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ─── TOKENIZER & CHUNKING ─────────────────────────────────────────────────────
tokenizer = tiktoken.get_encoding("cl100k_base")
def chunk_text(txt, max_toks=500, overlap=100):
    toks = tokenizer.encode(txt)
    return [
        tokenizer.decode(toks[i : i + max_toks])
        for i in range(0, len(toks), max_toks - overlap)
    ]

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

# ─── SIMPLE MODALITY DETECTION ────────────────────────────────────────────────
def detect_modality(query):
    if m := re.search(r'\bfig(?:ure)?\.?\s*(\d+)\b', query, re.I):
        return "figure", int(m.group(1))
    if m := re.search(r'\btable\.?\s*(\d+)\b', query, re.I):
        return "table", int(m.group(1))
    return "mixed", None

# ─── RAG SERVICE ───────────────────────────────────────────────────────────────
class RAGService:
    def __init__(self, pdf_id):
        # reference to the extracted content
        ec = ExtractedContent.objects.get(pdf__id=pdf_id)
        self.full_text   = ec.text
        self.table_items = ec.tables
        self.image_items = ec.images

        # where we’ll persist the FAISS index + metadata
        self.index_path = os.path.join(settings.MEDIA_ROOT, "indices", f"pdf_{pdf_id}.faiss")
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

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
            snippet = (
                df.head(5).to_json(orient="records")
                if not df.empty
                else json.dumps({"columns": list(df.columns)})
            )
            table_chunks.append({
                "content": f"Table p{tbl['page']}: {snippet}",
                "page": tbl["page"],
                "url": tbl["url"]
            })
        table_vecs = embed_text_chunks([t["content"] for t in table_chunks])

        # 3) embed images
        image_vecs = [embed_image(img["url"]) for img in self.image_items]

        # 4) assemble metadata array
        metadatas = []
        for c in text_chunks:
            metadatas.append({"type": "text",  "content": c})
        for t in table_chunks:
            metadatas.append({
                "type":    "table",
                "content": t["content"],
                "page":    t["page"],
                "url":     t["url"]
            })
        for img in self.image_items:
            metadatas.append({
                "type": "image",
                "page": img["page"],
                "url":  img["url"]
            })
        self.metadatas = metadatas

        # 5) build FAISS vector index
        all_vecs = np.vstack([
            np.array(text_vecs,  dtype="float32"),
            np.array(table_vecs, dtype="float32"),
            np.array(image_vecs, dtype="float32"),
        ])
        idx = faiss.IndexFlatL2(all_vecs.shape[1])
        idx.add(all_vecs)
        self.index = idx

        # 6) optionally persist to disk
        if persist:
            faiss.write_index(idx, self.index_path)
            with open(self.index_path + ".meta", "w") as f:
                json.dump(self.metadatas, f)

    def _load_index(self):
        # load FAISS index + metadata from disk
        idx = faiss.read_index(self.index_path)
        with open(self.index_path + ".meta") as f:
            metas = json.load(f)
        self.index     = idx
        self.metadatas = metas

    def retrieve(self, query, k=3):
        # lazy-load or (re)build the index
        if self.index is None:
            if self.index_exists():
                self._load_index()
            else:
                self.build_index(persist=True)

        # embed the query
        qv, = embed_text_chunks([query])
        D, I = self.index.search(np.array([qv], dtype="float32"), k * 5)

        # collect top k*5 hits with distances
        raw = [
            {"distance": float(D[0][i]), **self.metadatas[idx]}
            for i, idx in enumerate(I[0])
        ]

        # apply simple modality filtering
        mode, num = detect_modality(query)
        if mode == "figure":
            hits = [h for h in raw if h["type"]=="text" and re.search(fr'\bfig(?:ure)?\.?{num}\b', h["content"], re.I)][:k]
            if 1 <= num <= len(self.image_items):
                img = self.image_items[num-1]
                hits.append({"type":"image","page":img["page"],"url":img["url"]})
            return hits

        if mode == "table":
            hits = [h for h in raw if h["type"]=="text" and re.search(fr'\btable\.?{num}\b', h["content"], re.I)][:k]
            if 1 <= num <= len(self.table_items):
                tbl = self.table_items[num-1]
                hits.append({"type":"table","page":tbl["page"],"url":tbl["url"]})
            return hits

        # default: return top-k by distance
        return raw[:k]

    def ask_gemini(self, hits, question):
        # assemble Gemini contents
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
                contents.append(types.Part.from_bytes(
                    data=resp.content, mime_type="image/png"
                ))
        contents.append(f"QUESTION: {question}")

        resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents
        )
        return resp.text
