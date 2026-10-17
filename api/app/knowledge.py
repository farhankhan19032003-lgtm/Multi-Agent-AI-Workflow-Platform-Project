"""Document search over a company's uploaded policies, SOPs, contracts and manuals.

Default: dependency-free BM25 over text chunks (fast, no embeddings key needed).
Optional: LlamaIndex vector search when ENABLE_KNOWLEDGE=true and an embeddings key is set.
"""
import logging
import math
import re
from collections import Counter

from . import db
from .config import get_settings

log = logging.getLogger("knowledge")
_TOKEN = re.compile(r"[a-z0-9ऀ-ॿ]+")
_cache: dict[str, tuple[tuple, "_Index"]] = {}


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
            continue
        if cur:
            chunks.append(cur)
        while len(p) > size:  # very long paragraph
            chunks.append(p[:size])
            p = p[size - overlap:]
        cur = p
    if cur:
        chunks.append(cur)
    return chunks


class _Index:
    def __init__(self, docs: list[dict]):
        self.chunks: list[tuple[str, str]] = []
        for d in docs:
            for c in chunk_text(d["content"]):
                self.chunks.append((d["title"], c))
        self.toks = [Counter(_TOKEN.findall(c.lower())) for _, c in self.chunks]
        self.lens = [sum(t.values()) for t in self.toks]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        self.df: Counter = Counter()
        for t in self.toks:
            self.df.update(t.keys())

    def search(self, query: str, k: int) -> list[dict]:
        q = [w for w in _TOKEN.findall(query.lower()) if len(w) > 1]
        n = len(self.chunks)
        scored = []
        for i, tf in enumerate(self.toks):
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.lens[i] / self.avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [{"title": self.chunks[i][0], "text": self.chunks[i][1][:900], "score": round(s, 2)}
                for s, i in scored[:k]]


def _index(tenant_id: str) -> _Index | None:
    docs = db.table("documents").select("id,title,content").eq("tenant_id", tenant_id).execute().data
    if not docs:
        return None
    sig = tuple(sorted((d["id"], len(d["content"])) for d in docs))
    hit = _cache.get(tenant_id)
    if hit and hit[0] == sig:
        return hit[1]
    idx = _Index(docs)
    _cache[tenant_id] = (sig, idx)
    return idx


def has_documents(tenant_id: str) -> bool:
    return bool(db.table("documents").select("id").eq("tenant_id", tenant_id).limit(1).execute().data)


def search(tenant_id: str, question: str, k: int = 4) -> list[dict]:
    idx = _index(tenant_id)
    return idx.search(question, k) if idx else []


def lookup_sops(tenant_id: str, question: str, k: int = 2) -> list[dict]:
    """Backwards-compatible entry point (used by the v1 analytics agent)."""
    if get_settings().enable_knowledge:
        try:
            from llama_index.core import Document, VectorStoreIndex

            rows = db.table("documents").select("id,title,content").eq("tenant_id", tenant_id).execute().data
            if rows:
                index = VectorStoreIndex.from_documents(
                    [Document(text=r["content"], metadata={"title": r["title"]}) for r in rows])
                return [{"title": n.metadata.get("title"), "text": n.text[:600]}
                        for n in index.as_retriever(similarity_top_k=k).retrieve(question)]
        except Exception:
            log.exception("LlamaIndex lookup failed, falling back to BM25")
    return [{"title": h["title"], "text": h["text"][:600]} for h in search(tenant_id, question, k)]
