import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config.settings import settings
from app.providers import get_embeddings


COLLECTION = settings.qdrant_collection


def client() -> QdrantClient:
    kwargs: dict = {
        "url": settings.qdrant_url.rstrip("/"),
        "timeout": 30 if settings.qdrant_api_key else 5,
    }
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
        kwargs["https"] = settings.qdrant_url.startswith("https://")
    return QdrantClient(**kwargs)


def ensure_collection(dim: int = 64) -> None:
    try:
        c = client()
        existing = [x.name for x in c.get_collections().collections]
        if COLLECTION not in existing:
            c.create_collection(
                collection_name=COLLECTION,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )
    except Exception:
        return


def upsert_chunks(points: list[dict]) -> None:
    if os.environ.get("PROVE_SKIP_QDRANT") == "1":
        return
    if not points:
        return
    texts = [p["text"] for p in points]
    vectors = get_embeddings().embed(texts)
    ensure_collection(len(vectors[0]))
    c = client()
    qpoints = []
    for p, vec in zip(points, vectors):
        qpoints.append(
            qm.PointStruct(
                id=p["id"],
                vector=vec,
                payload={**p.get("metadata", {}), "text": p["text"]},
            )
        )
    c.upsert(collection_name=COLLECTION, points=qpoints)


def search(query: str, metadata_filter: dict | None = None, limit: int = 5) -> list[dict]:
    if os.environ.get("PROVE_SKIP_QDRANT") == "1":
        return []
    try:
        vec = get_embeddings().embed([query])[0]
        ensure_collection(len(vec))
    except Exception:
        return []
    must = []
    if metadata_filter:
        for k, v in metadata_filter.items():
            if v is None:
                continue
            if k == "effective_date_lte":
                must.append(qm.FieldCondition(key="effective_date", range=qm.Range(lte=None)))
                continue
            must.append(qm.FieldCondition(key=k, match=qm.MatchValue(value=v)))
    qfilter = qm.Filter(must=must) if must else None
    try:
        c = client()
        hits = c.search(
            collection_name=COLLECTION,
            query_vector=vec,
            query_filter=qfilter,
            limit=limit,
        )
    except Exception:
        return []
    return [{"id": str(h.id), "score": float(h.score), "payload": h.payload} for h in hits]
