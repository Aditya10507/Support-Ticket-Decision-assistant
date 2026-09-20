# Find matching policies using Gemini embeddings
import os
import json
import numpy as np
from dotenv import load_dotenv
from google import genai
from src.database import get_connection

# Load key from .env file
load_dotenv()

# Same model as ingest.py (must exist in ListModels)
EMBED_MODEL = "gemini-embedding-001"

# Keep chunks in memory so we load DB only once
_CACHE = None

# Compare two vectors, 1.0 = same meaning
def cosine_similarity(a, b) -> float:
    a = np.array(a)
    b = np.array(b)
    n = float(np.linalg.norm(a) * np.linalg.norm(b))
    if n == 0:
        return 0.0
    return float(np.dot(a, b) / n)

# Make embedding for ticket text
def embed_query(text: str) -> list[float]:
    # Read key each time
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Missing GEMINI_API_KEY")
    # Ask Gemini for vector
    client = genai.Client(api_key=key)
    res = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return list(res.embeddings[0].values)

# Load chunks from sqlite once
def load_knowledge_base():
    global _CACHE
    # Return saved copy if already loaded
    if _CACHE is not None:
        return _CACHE
    # Open DB and read all chunks
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT text, source, embedding FROM kb_chunks WHERE model = ?",
            (EMBED_MODEL,),
        ).fetchall()
    finally:
        conn.close()
    # Stop if ingest was not run
    if not rows:
        raise FileNotFoundError("No Gemini embeddings. Run: python ingest.py")
    # Parse JSON vectors once
    _CACHE = [
        {"text": r["text"], "source": r["source"], "vec": json.loads(r["embedding"])}
        for r in rows
    ]
    return _CACHE

# Main function used by api.py
def retrieve_relevant_chunks(ticket_message: str, top_k: int = 3) -> list[dict]:
    # Load cached policies
    chunks = load_knowledge_base()
    # Try to embed ticket, fallback to all policies on API fail
    try:
        q = embed_query(ticket_message)
    except Exception:
        # Return all policies with 0 score so LLM still has context
        return [{"text": c["text"], "source": c["source"], "score": 0.0} for c in chunks]
    # Score each chunk
    scored = []
    for c in chunks:
        s = cosine_similarity(q, c["vec"])
        scored.append({"text": c["text"], "source": c["source"], "score": round(s, 4)})
    # Best first
    scored.sort(key=lambda x: x["score"], reverse=True)
    # If best match is weak, return all policies for full context
    if not scored or scored[0]["score"] < 0.4:
        return scored
    return scored[:top_k]
