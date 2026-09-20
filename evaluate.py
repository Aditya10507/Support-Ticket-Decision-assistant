# Real evaluation: first 10 rows of data/tickets.csv through the full API
# (register -> login -> POST /tickets with REAL Gemini), temp DB so real data is safe.
# Prints spec format: total / Correct / Incorrect / Accuracy.
# 15 dataset actions map to 4 AI families (see EXPECTED_SETS), so match is loose.
import csv
import os
import sqlite3
import sys
import tempfile
import time

from fastapi.testclient import TestClient

import src.database as db
from src.api import app

APPROVE_SET = {"APPROVE_REFUND", "APPROVE_REPLACEMENT", "APPROVE_RETURN"}
APPROVE_FAMILY = {
    "APPROVE_REFUND_OR_REPLACEMENT", "APPROVE_RETURN", "APPROVE_REPLACEMENT",
    "REPLACE_CORRECT_ITEM", "CANCEL_AND_REFUND", "OFFER_REPLACEMENT_OR_REFUND",
}
EVIDENCE_FAMILY = {"REQUEST_PHOTOS", "REQUEST_DEFECT_EVIDENCE"}


def expected_set(resolved: str) -> set:
    if resolved in APPROVE_FAMILY:
        return APPROVE_SET
    if resolved in EVIDENCE_FAMILY:
        return {"REQUEST_PHOTOS"}
    if resolved == "NEEDS_MORE_INFORMATION":
        return {"NEEDS_MORE_INFORMATION"}
    return {"escalate", "deny_refund"}


def enrich(row) -> str:
    extra = []
    if row.get("order_value_inr"):
        extra.append(f"Order value Rs.{row['order_value_inr']}")
    if row.get("days_since_delivery"):
        extra.append(f"delivered {row['days_since_delivery']} days ago")
    if row.get("days_since_dispatch"):
        extra.append(f"dispatched {row['days_since_dispatch']} days ago")
    if row.get("product_type"):
        extra.append(f"product type {row['product_type']}")
    if row.get("opened_status"):
        extra.append(f"{row['opened_status']}")
    if row.get("order_status"):
        extra.append(f"order status {row['order_status']}")
    base = row.get("message", "")
    return base + (". " + ", ".join(extra) + "." if extra else "")


def main(n: int = 10):
    with open("data/tickets.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[:n]

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    old_url = db.DATABASE_URL
    db.DATABASE_URL = tmp.name
    correct = 0
    total = 0
    try:
        db.init_db()
        # Copy embeddings so temp DB can retrieve (else 500).
        try:
            src = sqlite3.connect(old_url)
            src.row_factory = sqlite3.Row
            chunks = src.execute("SELECT source, text, embedding, model, dim FROM kb_chunks").fetchall()
            src.close()
            if chunks:
                dst = sqlite3.connect(tmp.name)
                dst.executemany(
                    "INSERT INTO kb_chunks (source, text, embedding, model, dim) VALUES (?, ?, ?, ?, ?)",
                    [(c["source"], c["text"], c["embedding"], c["model"], c["dim"]) for c in chunks],
                )
                dst.commit()
                dst.close()
            else:
                print("WARNING: no kb_chunks. Run: python ingest.py")
        except Exception as e:
            print(f"KB copy failed: {e}")

        with TestClient(app, raise_server_exceptions=False) as client:
            client.post("/register", json={"email": "eval@test.com", "password": "test1234"})
            r = client.post("/login", json={"email": "eval@test.com", "password": "test1234"})
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            for row in rows:
                total += 1
                want = expected_set(row["resolved_action"])
                try:
                    resp = client.post("/tickets", json={"message": enrich(row)}, headers=headers)
                except Exception as e:
                    print(f"[{row['ticket_id']}] ERROR {e} want={sorted(want)}")
                    continue
                if resp.status_code != 201:
                    print(f"[{row['ticket_id']}] HTTP {resp.status_code} want={sorted(want)}")
                    continue
                got = resp.json()["decision"].get("action", "")
                mark = "OK" if got in want else "MISS"
                if mark == "OK":
                    correct += 1
                print(f"[{row['ticket_id']}] got={got} want~={sorted(want)} {mark}")
                time.sleep(3)  # stay under 5 req/min free tier
    finally:
        db.DATABASE_URL = old_url
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    wrong = total - correct
    acc = round(correct / total * 100) if total else 0
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {wrong}")
    print(f"Accuracy: {acc}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
