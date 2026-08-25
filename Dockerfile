# Project Atlas API image.
#
# Three things here are not incidental and should not be "simplified" away:
#
#  1. torch is installed from the PyTorch CPU index BEFORE requirements.lock.
#     requirements.lock was generated on Windows, so it carries no nvidia-*
#     pins. Installing torch==2.13.0 from PyPI on Linux therefore resolves the
#     CUDA build and drags in ~2.5 GB of CUDA runtime wheels this image will
#     never execute. Pre-satisfying torch from the CPU index brings the built
#     image in at ~700 MB, which is what makes it deployable on a free-tier
#     instance with a 30 GB disk.
#
#  2. The embedding and reranker weights are fetched at BUILD time. Loading
#     them on first request instead means a multi-second download inside the
#     request path, which surfaces to the user as embedding_unavailable (503).
#
#  3. tesseract-ocr is installed in the runtime stage. app/ingestion.py shells
#     out to it through pytesseract; the Python package is only a wrapper, so
#     without the binary scanned-PDF OCR fails at request time, not build time.

# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV HF_HOME=/opt/hf-cache

# build-essential is needed only while wheels compile. Keeping it out of the
# runtime stage is the entire reason this build is split in two.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Pin the CPU build first. If this version is ever absent from the CPU index
# the build fails loudly right here, which is the correct outcome - the
# alternative is a silent 2.5 GB CUDA image that no longer fits the disk.
RUN pip install --upgrade pip \
 && pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.lock ./
RUN pip install -r requirements.lock

# The project itself is deliberately NOT pip-installed. Nothing reads its
# installed distribution metadata (the only importlib.metadata call in the tree
# looks up qdrant-client), and the runtime imports it from source instead:
# WORKDIR is /app, the entrypoint runs `python3 -m uvicorn`, which puts the
# working directory on sys.path, and alembic.ini sets `prepend_sys_path = .`
# for the migration step. Skipping it also avoids a pip build-isolation step
# that has to reach PyPI for a backend Python 3.12 venvs no longer ship.

# Prefetch weights into HF_HOME so the runtime stage can copy them in.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); print('weights cached')"

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr curl \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH"
ENV HF_HOME=/opt/hf-cache
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TOKENIZERS_PARALLELISM=false

# The weights are already baked in, so refuse Hugging Face egress at runtime
# rather than letting a hub lookup add latency to a cold request.
ENV HF_HUB_OFFLINE=1

# Thread and allocator caps. torch sizes its thread pool to the host CPU count
# and every allocator arena costs resident memory; on a 1 GB free-tier instance
# this is the difference between serving and being OOM-killed. Raise them if
# you move to a larger instance.
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV MALLOC_ARENA_MAX=2

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-cache /opt/hf-cache

WORKDIR /app
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
# Runtime data, not test fixtures: app/api.py and app/evaluation.py resolve
# data/synthetic_epc relative to the package parent for ground truth,
# shipment records, and evaluation fixtures.
COPY data ./data
COPY alembic.ini pyproject.toml ./

RUN useradd --create-home --uid 10001 atlas \
 && mkdir -p /data/uploads /data/graphs \
 && chown -R atlas:atlas /data /app \
 && chmod +x scripts/start_production.sh

# Point uploads and the graph export at a mounted volume. The defaults
# (./uploads, ./graphs) are container-layer paths and would be lost on every
# redeploy - the durability gap recorded in docs/LIMITATIONS.md.
ENV ATLAS_UPLOAD_DIR=/data/uploads
ENV ATLAS_GRAPH_DIR=/data/graphs

USER atlas

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["./scripts/start_production.sh"]
