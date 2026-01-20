import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
from app.db import get_item, get_items_by_type, update_embedding, DB_PATH

# lazy-load model
_MODEL = None

def _get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL

def embed_text(text: str) -> List[float]:
    model = _get_model()
    emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return emb.tolist()

def ensure_item_embedding(item_id: int):
    item = get_item(item_id)
    if not item:
        raise ValueError("item not found")
    if item.get("embedding") is None:
        emb = embed_text(f"{item['title']}. {item.get('description') or ''}")
        update_embedding(item_id, emb)

def find_matches_for_item(item_id: int, top_k: int = 5) -> List[Dict]:
    item = get_item(item_id)
    if not item:
        raise ValueError("item not found")
    # determine opposite type
    opposite_type = "found" if item["type"].lower() == "lost" else "lost"
    candidates = get_items_by_type(opposite_type)
    # compute embeddings for candidates missing embeddings
    for c in candidates:
        if c.get("embedding") is None:
            emb = embed_text(f"{c['title']}. {c.get('description') or ''}")
            update_embedding(c["id"], emb)
            c["embedding"] = emb

    # ensure item embedding present
    if item.get("embedding") is None:
        item_emb = embed_text(f"{item['title']}. {item.get('description') or ''}")
        update_embedding(item_id, item_emb)
        item["embedding"] = item_emb

    if not candidates:
        return []

    item_vec = np.array(item["embedding"], dtype=float).reshape(1, -1)
    cand_vecs = np.vstack([np.array(c["embedding"], dtype=float) for c in candidates])
    sims = cosine_similarity(item_vec, cand_vecs)[0]
    # pair and sort
    paired = list(zip(candidates, sims))
    paired.sort(key=lambda x: x[1], reverse=True)
    top = paired[:top_k]
    results = []
    for c, score in top:
        results.append({
            "id": c["id"],
            "title": c["title"],
            "description": c["description"],
            "type": c["type"],
            "location": c["location"],
            "score": float(score)
        })
    return results