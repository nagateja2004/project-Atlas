# Deployment

Two supported targets. They are alternatives, not layers - pick one.

| Target | Shape | Guide |
| --- | --- | --- |
| **AWS** | One EC2 instance runs API, dashboard, PostgreSQL, Qdrant and Caddy in Docker Compose. Images built by GitHub Actions, pulled by the instance. Runs on the free tier. | [docs/AWS_DEPLOY.md](docs/AWS_DEPLOY.md) |
| **Render + Vercel** | Managed API on Render, dashboard on Vercel, PostgreSQL on Supabase, Qdrant Cloud. | The rest of this file |

The AWS path is self-contained: it needs no Supabase, no Qdrant Cloud, and no
Vercel, because it hosts those components itself. It also fixes two constraints
listed at the bottom of this file - uploaded documents and the graph export are
durable there, since both are on named volumes rather than an ephemeral
container filesystem.

## Render + Vercel

### Services

- **Vercel:** deploy `frontend` as the project Root Directory. Its browser client calls FastAPI through `NEXT_PUBLIC_API_URL`.
- **Render:** create the API service from [`render.yaml`](render.yaml). Render supplies `PORT`; the start command runs `alembic upgrade head` before `uvicorn app.main:app --port $PORT`. The build installs `requirements.lock` (not the `>=` floors in `pyproject.toml`) so a deploy matches what CI tested, and pre-fetches the embedding and reranker weights so the first query is not a multi-second download.
- **Supabase:** provide the PostgreSQL connection as an async SQLAlchemy `DATABASE_URL` (`postgresql+asyncpg://…`); Supabase Auth and Storage variables remain backend-only.
- **Qdrant Cloud:** configure `QDRANT_URL` and `QDRANT_API_KEY` on Render.
- **Model providers:** FastAPI reads `ATLAS_LLM_PROVIDERS` (an ordered, comma-separated list) plus one API key per provider, and fails over on rate limits or outages. Configure at least two: free tiers have small daily caps, and a single exhausted provider otherwise takes generation down until it resets. The frontend never calls a provider directly.

### Environment variables

| Service | Variables |
| --- | --- |
| Render backend | `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `JWT_SECRET_KEY`, `FRONTEND_URL` |
| Vercel frontend | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |

Never put `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`, `GROQ_API_KEY`, or `JWT_SECRET_KEY` in Vercel. Do not create `NEXT_PUBLIC_GROQ_API_KEY`.

### Deploy commands

```bash
# Render start command (configured by render.yaml)
./scripts/start_production.sh

# Run migrations manually, if needed
alembic upgrade head

# Seed or refresh the idempotent synthetic demo after the API is healthy
python3 scripts/seed_demo.py --api-url "$NEXT_PUBLIC_API_URL"

# Reset the project-scoped synthetic state, then restore the vertical scenario
curl -fsS -X POST "$NEXT_PUBLIC_API_URL/projects/$PROJECT_ID/demo/reset"
curl -fsS -X POST "$NEXT_PUBLIC_API_URL/projects/$PROJECT_ID/demo/vertical-scenario"
```

Vercel auto-detects Next.js when its Root Directory is `frontend`; no `vercel.json` is needed. Set `NEXT_PUBLIC_API_URL` to the Render API URL before building. Set `FRONTEND_URL` on Render to the matching Vercel URL so FastAPI permits only that browser origin.

### Release check

After deployment, request `GET /health` for liveness and `GET /ready` for database/Qdrant readiness. Project filters are enforced by the existing project-scoped API services; deploy behind an authenticated gateway until application authentication is enabled.

### Deployment constraints to plan around

- **Uploaded documents and the graph export are not durable.** `ATLAS_UPLOAD_DIR` and `ATLAS_GRAPH_DIR` write to the container filesystem, which Render replaces on every deploy and restart. Database rows survive; the original files behind their citations do not. Re-seed after a deploy, or attach a disk / move originals to object storage first.
- **Changing the embedding model or dimensions invalidates the Qdrant collection.** Ingestion then returns `embedding_dimension_mismatch` (409) instead of storing incomparable vectors. Delete the collection and reindex with `--force`, or point `ATLAS_QDRANT_COLLECTION` at a new name. See the migration section in [README.md](README.md).
- **Model weights are fetched at build time and cached in the image.** A cold build downloads roughly 100 MB. If the build cannot reach Hugging Face, set `ATLAS_EMBEDDING_BACKEND=local_hash` to boot without them — but retrieval is then lexical only and will not match paraphrased questions.
- **Ingestion is synchronous.** A large scanned PDF holds its upload connection for the duration of OCR, bounded by `ATLAS_INGESTION_TIMEOUT_SECONDS` (default 300). Set the platform request timeout above that value, or uploads will be cut off by the proxy before the service can respond.
- **Authentication is available but off by default.** Set `ATLAS_AUTH_ENABLED=true` and a `JWT_SECRET_KEY`, then create an account with `python scripts/create_user.py`. Passwords are hashed with `hashlib.scrypt` and session tokens are HMAC-SHA256 signed, both from the standard library. A user is global; `project_members` grants **viewer**, **reviewer** or **admin** per project. Reading needs viewer, mutating needs reviewer, managing members needs admin. A non-member receives **404, not 403**, because a 403 would confirm the project exists. **With it disabled**, `project_id` filtering is data scoping rather than authorization and any caller who can reach the service can read every project — so an unconfigured deployment must stay behind an authenticated gateway. Tokens cannot be revoked before they expire, there is no password-reset flow, and `/auth/login` is not rate-limited.
