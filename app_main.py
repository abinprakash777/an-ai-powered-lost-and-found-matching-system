from fastapi import FastAPI, HTTPException
from typing import List
from app.models import ItemCreate, ItemOut, MatchOut
from app.db import init_db, create_item, get_item, get_items_by_type, update_embedding, DB_PATH
from app.matcher import embed_text, ensure_item_embedding, find_matches_for_item

app = FastAPI(title="Lost & Found Matcher (minor project)")

# initialize DB (file at DB_PATH)
init_db(DB_PATH)

@app.post("/items", response_model=ItemOut)
def add_item(item: ItemCreate):
    item_id = create_item(item)
    # compute and save embedding async-like (quick synchronous for simplicity)
    embedding = embed_text(f"{item.title}. {item.description or ''}")
    update_embedding(item_id, embedding)
    stored = get_item(item_id)
    return stored

@app.get("/items/{item_id}", response_model=ItemOut)
def read_item(item_id: int):
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/matches/{item_id}", response_model=List[MatchOut])
def get_matches(item_id: int, top_k: int = 5):
    # ensures embeddings exist for the item and computes others as needed
    ensure_item_embedding(item_id)
    matches = find_matches_for_item(item_id, top_k=top_k)
    return matches