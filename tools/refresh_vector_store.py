from sentence_transformers import SentenceTransformer
import faiss
import json
import numpy as np

MODEL = SentenceTransformer("all-MiniLM-L6-v2")
DIM = MODEL.get_sentence_embedding_dimension()
index = faiss.IndexFlatIP(DIM)
pairs = []

with open("good_pairs.jsonl", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        obj = json.loads(line)
        user = obj.get("user", "")
        reply = obj.get("reply", "")
        # Skip if user or reply is missing or too short
        if not isinstance(user, str) or not isinstance(reply, str):
            print(f"Line {idx}: Skipped, user or reply not a string.")
            continue
        if len(user.strip()) < 3 or len(reply.strip()) < 3:
            print(f"Line {idx}: Skipped, user or reply too short.")
            continue
        emb = MODEL.encode([user])
        # Normalize embedding for cosine similarity
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        index.add(emb)
        pairs.append({"user": user, "reply": reply})
        print(f"Line {idx}: Added pair.")

faiss.write_index(index, "retrieval.index")
print("FAISS index written to retrieval.index")
with open("retrieval_pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f)
print("Pairs written to retrieval_pairs.json")
print("Refreshed FAISS index and pairs.")