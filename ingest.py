# Make Gemini embeddings once and save to sqlite
import os
import json
from dotenv import load_dotenv
from google import genai
from src.database import get_connection, init_db

# Load key from .env file
load_dotenv()

# Folder with policy files
KB_DIR = "knowledge_base"
# Gemini embedding model name (must exist in ListModels)
EMBED_MODEL = "gemini-embedding-001"

# Split text into small pieces
def split_chunks(text: str) -> list[str]:
    # Split by blank lines
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    return parts if parts else [text.strip()]

# Make one embedding with Gemini
def embed_one(client, text: str) -> list[float]:
    # Ask Gemini for vector
    res = client.models.embed_content(model=EMBED_MODEL, contents=text)
    # Take first vector from answer
    return list(res.embeddings[0].values)

# Main work: read files, embed, save
def main():
    # Check key exists
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("Missing GEMINI_API_KEY in .env")
        return
    # Make tables if missing
    init_db()
    # Make Gemini client
    client = genai.Client(api_key=key)
    # Open DB
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Clear old rows for this model
        cur.execute("DELETE FROM kb_chunks WHERE model = ?", (EMBED_MODEL,))
        # Read each .md file
        count = 0
        for fname in os.listdir(KB_DIR):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(KB_DIR, fname), encoding="utf-8") as f:
                text = f.read()
            # Embed each chunk
            for chunk in split_chunks(text):
                vec = embed_one(client, chunk)
                # Save chunk + vector as JSON text
                cur.execute(
                    "INSERT INTO kb_chunks (source, text, embedding, model, dim) VALUES (?, ?, ?, ?, ?)",
                    (fname, chunk, json.dumps(vec), EMBED_MODEL, len(vec)),
                )
                count += 1
                print(f"Saved {fname} chunk {count}")
        conn.commit()
        print(f"Done! {count} chunks saved with {EMBED_MODEL}.")
    finally:
        # Always close DB
        conn.close()

# Run only when file is run directly
if __name__ == "__main__":
    main()
