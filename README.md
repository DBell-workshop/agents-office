# Ecommerce AI Lab Prototype

This repository contains a phase-1 prototype for two scenarios:

- In-store sales training
- Cross-platform offer comparison

The prototype is intentionally lightweight and built for lab validation.

## Tech Stack

- FastAPI backend
- Static web frontend
- In-memory storage (no database yet)
- Mock services for LLM/TTS/ASR/OpenClaw by default

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Environment Variables

- `OPENCLAW_MODE`: `mock` (default) or `remote`
- `OPENCLAW_REMOTE_BASE_URL`: remote collector URL when `OPENCLAW_MODE=remote`
- `OPENCLAW_TIMEOUT_SECONDS`: request timeout for remote collector

## Run Tests

```bash
pytest -q
```

## Smoke Check

```bash
bash scripts/smoke_test.sh
```
