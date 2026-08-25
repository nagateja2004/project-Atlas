# Licenses and third-party notices

## Project license status

The repository is MIT licensed; see the root [`LICENSE`](../LICENSE). Confirm MIT remains compatible with every distributed dependency before publishing — in particular PyMuPDF, whose terms are noted below.

## Direct dependencies

This summary is based on `pyproject.toml`, `requirements.lock`, `requirements-dev.lock`, `frontend/package-lock.json`, and installed package metadata. It is not legal advice. Exact notices shipped with the resolved packages remain authoritative.

| Component | Declared license |
| --- | --- |
| FastAPI, Alembic, LangGraph, Pydantic Settings, SQLAlchemy | MIT |
| asyncpg, OpenAI Python SDK, python-multipart, qdrant-client, sentence-transformers, transformers, huggingface-hub | Apache-2.0 |
| NetworkX, Uvicorn, PyTorch, NumPy, SciPy | BSD family |
| Pillow | MIT-CMU |
| pytesseract | Apache-2.0 |
| PyMuPDF | AGPL-3.0 or Artifex commercial license |
| Next.js, React, React DOM, Tailwind CSS, Vitest, ESLint | MIT |
| TypeScript | Apache-2.0 |
| PostgreSQL | PostgreSQL License |
| Qdrant server | Apache-2.0 |

PyMuPDF’s distribution terms require explicit review before public distribution or a proprietary deployment. OCR also requires a separately installed Tesseract executable; its own license and language-data notices must be retained by the distributor.

## Data and assets

The synthetic EPC corpus and repository-authored diagrams/backup SVGs were created for this prototype. They contain no licensed standards text or claimed third-party project records. No permission for reuse is granted until a root project license is selected.

Before submission, run the lockfile/license review again, retain required notices, add the approved root license, and record any pitch-deck fonts, icons, screenshots, music, or stock assets not stored in this repository.

## Model weights

Retrieval and reranking download model weights at first use, which are licensed separately from the code that loads them:

| Model | Role | Declared license |
| --- | --- | --- |
| `sentence-transformers/all-MiniLM-L6-v2` | dense embeddings | Apache-2.0 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | reranking | Apache-2.0 |

Weights are fetched from Hugging Face at runtime and are not redistributed in this repository. A deployment that vendors them must retain their model cards and licenses.
Model providers are accessed as hosted APIs through the OpenAI-compatible wire format; each provider's own terms govern use, and no provider model weights are distributed here.
