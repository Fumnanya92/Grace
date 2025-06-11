from sentence_transformers import SentenceTransformer
import faiss, threading

MODEL = SentenceTransformer("all-MiniLM-L6-v2")
DIM   = MODEL.get_sentence_embedding_dimension()
index = faiss.IndexFlatIP(DIM)
pairs = []                          # keeps (user, reply) text in RAM
lock  = threading.Lock()

def add_pair(user, reply):
    emb = MODEL.encode([user])
    with lock:
        index.add(emb)
        pairs.append((user, reply))

def search(query, k=3, thresh=0.83):
    emb = MODEL.encode([query])
    D, I = index.search(emb, k)
    results = [
        pairs[i] for d, i in zip(D[0], I[0])
        if d > thresh
    ]
    return results
