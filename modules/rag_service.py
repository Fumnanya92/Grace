# rag_service.py
import json
import os

CATALOG_PATH = "catalog_store.json"

def load_catalog():
    if not os.path.exists(CATALOG_PATH):
        return []
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)

def inject_catalog_context(prompt: str) -> str:
    catalog = load_catalog()
    context_lines = [f"{item['name']} - {item['price']} - {item['description']}" for item in catalog[:5]]
    context_blob = "\n".join(context_lines)
    return f"Context:\n{context_blob}\n\nUser: {prompt}"
