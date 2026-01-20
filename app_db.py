import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models import ItemCreate

DB_PATH = "data.db"

def _connect():
    return sqlite3.connect(DB_PATH)

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            location TEXT,
            embedding TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def create_item(item: ItemCreate) -> int:
    conn = _connect()
    cur = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO items (title, description, type, location, created_at) VALUES (?, ?, ?, ?, ?)",
        (item.title, item.description, item.type, item.location, created_at),
    )
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return item_id

def update_embedding(item_id: int, embedding) -> None:
    conn = _connect()
    cur = conn.cursor()
    emb_text = json.dumps([float(x) for x in embedding])
    cur.execute("UPDATE items SET embedding = ? WHERE id = ?", (emb_text, item_id))
    conn.commit()
    conn.close()

def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "type": row[3],
        "location": row[4],
        "embedding": row[5],
        "created_at": row[6],
    }

def get_item(item_id: int) -> Optional[Dict]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, type, location, embedding, created_at FROM items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = _row_to_dict(row)
    # convert embedding to list if present
    if d["embedding"]:
        d["embedding"] = json.loads(d["embedding"])
    return d

def get_items_by_type(type_value: str) -> List[Dict]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, type, location, embedding, created_at FROM items WHERE type = ?", (type_value,))
    rows = cur.fetchall()
    conn.close()
    out = []
    for row in rows:
        d = _row_to_dict(row)
        if d["embedding"]:
            d["embedding"] = json.loads(d["embedding"])
        out.append(d)
    return out