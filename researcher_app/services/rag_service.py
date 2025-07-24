# researcher_app/services/rag_service.py

import os, json, requests, base64, numpy as np, pandas as pd, faiss
from django.conf import settings
from researcher_app.models import ExtractedContent
import tiktoken
from google import genai
from google.genai import types

# Env‐driven endpoints
TEXT_EMBED_URL  = os.environ["CLIP_TEXT_EMBED_URL"]
IMAGE_EMBED_URL = os.environ["CLIP_IMAGE_EMBED_URL"]
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
gemini_client   = genai.Client(api_key=GEMINI_API_KEY)

# Tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")
def chunk_text(txt, max_toks=500, overlap=100):
    toks = tokenizer.encode(txt)
    return [tokenizer.decode(toks[i : i + max_toks])
            for i in range(0, len(toks), max_toks - overlap)]

# Embedders
def embed_text_chunks(chunks):
    resp = requests.post(TEXT_EMBED_URL, json={"texts": chunks})
    resp.raise_for_status()
    return resp.json()["embeddings"]

def embed_image(path_or_url):
    # … same as before …
    pass

class RAGService:
    def __init__(self, pdf_id):
        self.pdf_id    = pdf_id
        ec             = ExtractedContent.objects.get(pdf__id=pdf_id)
        self.text      = ec.text
        self.tables    = ec.tables
        self.images    = ec.images

        # path to store your FAISS index + metadata
        self.index_path = os.path.join(settings.MEDIA_ROOT, f"indices/pdf_{pdf_id}.faiss")
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        self.index     = None
        self.metadatas = None

    def index_exists(self):
        return os.path.isfile(self.index_path)

    def build_index(self, persist=False):
        # 1) chunk & embed text
        text_chunks = chunk_text(self.text)
        text_vecs   = embed_text_chunks(text_chunks)

        # 2) tables & images → similar embedding
        # …

        # 3) assemble all vectors + metadata
        all_vecs  = np.vstack([np.array(text_vecs, dtype="float32")])
        dim       = all_vecs.shape[1]
        idx       = faiss.IndexFlatL2(dim)
        idx.add(all_vecs)
        self.index     = idx
        self.metadatas = [{"type":"text","content":c} for c in text_chunks]

        # 4) persist to disk if requested
        if persist:
            faiss.write_index(idx, self.index_path)
            with open(self.index_path + ".meta", "w") as f:
                json.dump(self.metadatas, f)

    def _load_index(self):
        self.index      = faiss.read_index(self.index_path)
        with open(self.index_path + ".meta") as f:
            self.metadatas = json.load(f)

    def retrieve(self, query, k=3):
        # lazy‐load or (re)build
        if self.index is None:
            if self.index_exists():
                self._load_index()
            else:
                self.build_index(persist=True)

        qv, = embed_text_chunks([query])
        D, I = self.index.search(np.array([qv],dtype="float32"), k)
        return [{"distance": float(D[0][i]), **self.metadatas[i]} for i in I[0]]

    def ask_gemini(self, hits, question):
        # assemble multimodal “contents” list …
        resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents
        )
        return resp.text
