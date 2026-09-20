# Development Guide

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
```

## Ingest Knowledge Base
```bash
python ingest.py
```

## Run API
```bash
uvicorn src.api:app --reload
```

## Run Frontend
```bash
streamlit run streamlit_app.py
```

## Run Evaluation
```bash
python evaluate.py
```

## Run Tests
```bash
pytest tests/ -v
```

## AI Agent Usage
- Tool: Muse Spark via OpenCode for bug fixes and refactors.
- Used for: auth expiry fix, DB close fix, Gemini embeddings switch, tests.
- Human check: ran `py_compile`, `pytest`, `evaluate.py` after each fix.
- No blind copy: each agent edit was read and tested before keeping.
