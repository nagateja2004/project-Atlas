#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Set GEMINI_API_KEY, then rerun ./scripts/start_demo.sh."
  exit 1
fi
if ! grep -Eq '^(GEMINI_API_KEY|ATLAS_GEMINI_API_KEY)=.+$' .env; then
  echo "GEMINI_API_KEY is required for live answer generation."
  exit 1
fi

python3 -m pip install -e '.[dev]'
(cd frontend && npm ci)
docker compose up -d
for _ in {1..60}; do
  if docker compose exec -T postgres pg_isready -U atlas -d atlas >/dev/null 2>&1 && curl -fsS http://localhost:6333/collections >/dev/null; then
    break
  fi
  sleep 1
done

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT
for _ in {1..30}; do
  if curl -fsS http://localhost:8001/ready >/dev/null; then break; fi
  sleep 1
done
python3 scripts/seed_demo.py --api-url http://localhost:8001
(cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8001 npm run dev)
