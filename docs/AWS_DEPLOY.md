# Deploying Project Atlas on AWS

One EC2 instance runs the whole stack in Docker Compose: the FastAPI API, the
Next.js dashboard, PostgreSQL, Qdrant, and Caddy for TLS. Images are built by
GitHub Actions and pulled by the instance, so a push to `main` becomes a live
deploy.

```
                        ┌──────────────────────────────────────────┐
  push to main          │  EC2 t3.micro · Amazon Linux 2023        │
       │                │                                          │
       ▼                │   caddy :80/:443  ── automatic TLS       │
  GitHub Actions        │     ├─ /projects/* /api/* /health /ready │
  (CI must pass)        │     │      └──▶ api :8000  (FastAPI)     │
       │                │     └─ everything else                   │
       ├─ build API ────┼──▶  │           └──▶ web :3000 (Next.js) │
       ├─ build web ────┼──▶  │                                    │
       │   to ghcr.io   │   postgres :5432 ─┐                      │
       │                │   qdrant   :6333 ─┴ internal network only│
       └─ ssh: pull ────┼──▶                                       │
                        │   volumes: uploads · graphs · pgdata ·   │
                        │            qdrant · caddy certs          │
                        └──────────────────────────────────────────┘
```

## Why this shape

- **One instance, not Elastic Beanstalk or Fargate.** Atlas needs PostgreSQL,
  Qdrant, *and* the `tesseract` binary. Elastic Beanstalk's Python platform
  cannot install tesseract and cannot host Qdrant at all, so it would force a
  separate RDS instance plus a paid Qdrant host. Fargate works but adds an ALB
  and a NAT gateway, neither of which is free-tier eligible.
- **Images are built in CI, not on the box.** The API image compiles wheels and
  bakes ~100 MB of model weights. A 1 vCPU / 1 GB instance either OOMs or takes
  tens of minutes doing that. GitHub Actions builds it in a few minutes and the
  instance only pulls.
- **Both services behind one origin.** `app/api.py` mounts routers at both
  `/projects` and `/api/*`, so Caddy matches the API prefixes verbatim and lets
  everything else fall through to Next.js. Because
  [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts) already falls back to
  same-origin in production, **no API hostname is baked into the bundle** — the
  instance address can change without rebuilding the frontend, and CORS is
  never exercised.

## Cost on the AWS free tier

| Component | Free tier | Notes |
| --- | --- | --- |
| EC2 `t3.micro` | 750 h/month for 12 months | One instance running continuously is ~730 h |
| EBS `gp3` 30 GB | 30 GB/month for 12 months | Holds images, Postgres, Qdrant, uploads |
| Data transfer out | 100 GB/month | A demo is nowhere near this |
| Elastic IP | Free **while attached** to a running instance | Billed if you allocate one and leave it unattached |
| ghcr.io images | Free for public repositories | Avoids ECR, whose free storage is only 500 MB |
| GitHub Actions | 2,000 min/month private, unlimited public | The API build dominates; layer caching keeps it short |

Everything above is $0 on a 12-month free-tier account. Two caveats worth
knowing before relying on that number:

- **Free-tier eligibility depends on your account age.** Accounts created
  before 15 July 2025 have the classic 12-month free tier described above.
  Newer accounts get a credit-based plan instead — the same architecture still
  runs, it just draws down credits. Check **Billing → Free tier** in the
  console for which one you have.
- **Set a budget alarm regardless.** Billing → Budgets → a $1 monthly cost
  budget with an alert. It costs nothing and it is the only thing that will
  tell you if something slipped outside the free tier.

## The one real constraint: memory

`t3.micro` has **1 GB of RAM**. Measured on this image, with both MiniLM models
loaded in-process after serving a query:

| Container | Resident |
| --- | --- |
| `api` (torch + embedding + reranker) | ~570 MB |
| `qdrant` | ~60 MB |
| `postgres` | ~40 MB |
| `web` (Next.js) | ~80 MB |
| `caddy` | ~20 MB |
| **total** | **~770 MB** |

So it does fit in 1 GB, but with only a couple of hundred megabytes of headroom
— not enough to absorb a concurrent ingestion, which loads page images for OCR.
Three things make that headroom workable, and all three are already configured:

1. **4 GB swap** ([`deploy/bootstrap-ec2.sh`](../deploy/bootstrap-ec2.sh)). This
   is the safety margin: an OCR-heavy upload that would otherwise be OOM-killed
   mid-request gets slow instead of fatal.
2. **Thread and allocator caps** (`OMP_NUM_THREADS=1`, `MALLOC_ARENA_MAX=2` in
   the [`Dockerfile`](../Dockerfile)). `torch` otherwise sizes its thread pool
   to the host CPU count, and each allocator arena costs resident memory.
3. **A single uvicorn worker** (`WEB_CONCURRENCY=1`). A second worker loads a
   second full copy of both models.

Expect the **first** retrieval query after a restart to take a few seconds while
the models load. Subsequent queries are normal.

**If you hit OOM restarts under load, resize to `t3.small` (2 GB).** Stop the
instance, change the instance type, start it — roughly $15/month, and nothing
else changes. For a judged demo where you control the pace, `t3.micro` is
genuinely enough; the case for `t3.small` is uploading large scanned PDFs live.

---

## Two ways to do Part 1

**Scripted**, if you have the AWS CLI with working credentials:

```bash
export AWS_REGION=ap-south-1          # pick the region nearest your judges
export REPO_URL=https://github.com/<you>/ET_HACKTON_MAIN.git
./deploy/provision-aws.sh
```

It creates the key pair, security group (SSH locked to your current IP), a
`t3.micro` with a 30 GB encrypted gp3 root volume, and an Elastic IP, then
prints the exact SSH and GitHub-secret values to use next. Every step checks
for an existing resource first, so re-running after a failure continues rather
than duplicating. `./deploy/teardown-aws.sh` removes all of it.

**By hand in the console**, if you would rather not install the CLI or issue an
access key — Part 1 below. Both end at the same place; skip to Part 2 if you
used the script.

## Part 1 — Launch the instance (console, ~10 minutes)

No AWS CLI needed.

1. **EC2 → Launch instance.**
   - Name: `atlas`
   - AMI: **Amazon Linux 2023** (free-tier eligible)
   - Instance type: **t3.micro** — confirm it shows *Free tier eligible*
   - Key pair: **create a new one**, type **ED25519**, format `.pem`. Download
     it and keep it; you cannot download it again.
   - Storage: change the root volume to **30 GiB gp3**. The 8 GiB default is
     too tight once the ~700 MB API image, Postgres, Qdrant and a spare
     image generation are all on disk.

2. **Network settings → Edit.** Create a security group with:

   | Type | Port | Source | Why |
   | --- | --- | --- | --- |
   | SSH | 22 | **My IP**, or Anywhere if you want auto-deploy — see below | |
   | HTTP | 80 | Anywhere | Also how Let's Encrypt validates the certificate |
   | HTTPS | 443 | Anywhere | |

   **SSH source and auto-deploy pull in opposite directions.** `My IP` is the
   safer setting, but the GitHub Actions deploy in Part 4 connects from rotating
   Azure runner addresses, so it will fail with
   `ssh: connect to host ... port 22: Connection timed out`. Allowing GitHub's
   published ranges instead is not workable: there are thousands of CIDRs, they
   rotate, and a security group caps at 60 rules.

   So pick one:

   - **Manual deploys only** - keep `My IP`. Deploy by hand over SSH; the
     workflow's build stage still publishes images.
   - **Auto-deploy** - set SSH to `0.0.0.0/0`. Amazon Linux 2023 ships with
     `PasswordAuthentication no`, so the only way in is your ED25519 key and
     there is no password to brute-force. The real cost is scanner noise in
     the logs. Tighten it back afterwards.
   - **Neither compromise** - drive the rollout through AWS SSM Session Manager
     instead of SSH. No inbound port at all, but it needs an IAM instance
     profile and AWS credentials in GitHub secrets. A self-hosted runner on the
     instance also avoids inbound SSH, but needs ~200 MB and will not fit
     alongside the API on `t3.micro`.

   Do **not** open 5432 or 6333. Postgres and Qdrant are reachable only on the
   Docker network, and there is no application-level authentication in front of
   them.

3. **Advanced details → User data.** Paste exactly this:

   ```bash
   #!/bin/bash
   set -eux
   dnf install -y git
   curl -fsSL https://raw.githubusercontent.com/mahendraaravind13-creator/project-Atlas/main/deploy/bootstrap-ec2.sh -o /tmp/bootstrap.sh
   bash /tmp/bootstrap.sh
   ```

   Fetching the script beats pasting it. Pasting 100+ lines from a Windows
   checkout carries CRLF line endings into cloud-init, and every line then fails
   with `$'
': command not found`; the raw URL always serves LF.

   Do **not** add `curl` to that `dnf install`. Amazon Linux 2023 ships
   `curl-minimal`, which already provides the `curl` binary, and installing the
   full `curl` package is a hard dnf conflict - with `set -e` the whole
   bootstrap aborts before it does anything.

   The script creates swap, installs Docker and the Compose plugin, caps
   container log size, and clones the repo to `/opt/atlas`. It deliberately
   does **not** start anything - secrets must not go into user data, which any
   process on the instance can read back from the metadata service.

4. **Launch**, then **allocate an Elastic IP** (EC2 → Elastic IPs → Allocate)
   and **associate it with the instance**. Without one, the public IP changes
   on every stop/start and your TLS hostname breaks. It is free while attached.

## Part 2 — Configure and start (~10 minutes)

```bash
chmod 400 atlas.pem
ssh -i atlas.pem ec2-user@<ELASTIC-IP>

# Confirm bootstrap finished. Expect ~4 GB of swap and a docker version.
free -h && docker --version && docker compose version
```

Generate the two secrets, then fill in the env file:

```bash
openssl rand -hex 24    # POSTGRES_PASSWORD
openssl rand -hex 24    # QDRANT_API_KEY

cd /opt/atlas
nano .env.aws
```

Set at minimum — the compose file refuses to start if any are missing:

```ini
ATLAS_PUBLIC_URL=http://<ELASTIC-IP>
POSTGRES_PASSWORD=<first generated value>
QDRANT_API_KEY=<second generated value>
GROQ_API_KEY=<your key>
OPENROUTER_API_KEY=<a second provider, see below>
```

Configure a **second** provider. Free LLM tiers have small daily caps, and a
single exhausted provider takes answer generation down until it resets. The
router in `app/llm.py` fails over automatically and skips any provider whose
key is absent, so a second key is free insurance.

Start it. This first run builds locally, which is slow on `t3.micro` — once the
GitHub Actions deploy is wired up (Part 4), rollouts pull instead of build.

```bash
docker compose -f docker-compose.aws.yml --env-file .env.aws up -d --build
docker compose -f docker-compose.aws.yml --env-file .env.aws logs -f api
```

`alembic upgrade head` runs in the container entrypoint before uvicorn, so the
schema is applied on first boot. Verify:

```bash
curl -fsS localhost/health      # {"status":"ok",...}
curl -fsS localhost/ready       # database and qdrant both "ok"
```

Then open `http://<ELASTIC-IP>` in a browser.

## Part 3 — Free HTTPS, without buying a domain

Caddy will provision a real Let's Encrypt certificate for any hostname that
resolves to your IP. `sslip.io` gives you one for free: take the Elastic IP and
replace the dots with dashes.

For `13.51.2.3` the hostname is `13-51-2-3.sslip.io`. In `.env.aws`:

```ini
ATLAS_SITE_ADDRESS=13-51-2-3.sslip.io
ATLAS_ACME_EMAIL=you@example.com
ATLAS_PUBLIC_URL=https://13-51-2-3.sslip.io
```

```bash
docker compose -f docker-compose.aws.yml --env-file .env.aws up -d
docker compose -f docker-compose.aws.yml --env-file .env.aws logs -f caddy
```

Port 80 must stay open to the internet — that is how the ACME HTTP challenge
validates. Certificates are kept in the `caddy_data` volume; do not delete it,
or every restart re-requests from Let's Encrypt and will eventually hit its
rate limit.

## Part 4 — Push-to-deploy

[`.github/workflows/deploy-aws.yml`](../.github/workflows/deploy-aws.yml) runs
on `workflow_run` after **CI succeeds** on `main`, so a failing build cannot
reach the instance. It builds both images, pushes them to `ghcr.io`, then SSHes
in to pull and roll out.

Create an SSH key dedicated to deployment rather than reusing your login key:

```bash
# on your machine
ssh-keygen -t ed25519 -f atlas-deploy -N ""
ssh-copy-id -i atlas-deploy.pub -o IdentityFile=atlas.pem ec2-user@<ELASTIC-IP>
cat atlas-deploy          # the private key, for the secret below
```

In GitHub → **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
| --- | --- |
| `EC2_HOST` | your Elastic IP |
| `EC2_USER` | `ec2-user` |
| `EC2_SSH_KEY` | the full contents of `atlas-deploy`, including the BEGIN/END lines |

No AWS access keys are needed — the deploy is SSH, not an AWS API call.

If the repository is **private**, its GHCR packages are private too; the
workflow logs the instance in with the run's `GITHUB_TOKEN`, which is already
handled.

One thing to know about `workflow_run`: GitHub always takes the workflow
definition from the **default branch**, so the deploy job does not exist until
`deploy-aws.yml` is merged to `main`. Testing it on a feature branch will
appear to do nothing.

Trigger the first run from **Actions → Deploy to AWS → Run workflow**. After
that, `git push origin main` → CI → deploy. The job polls `/ready` and fails
with the API logs attached if the new version does not come up.

To roll back, re-run the deploy workflow from the last good commit; every image
is tagged with its commit SHA in GHCR.

## Part 5 — Seed the demo

Uploaded files live in the `atlas_uploads` volume and survive redeploys, but a
fresh instance starts empty:

```bash
cd /opt/atlas
docker compose -f docker-compose.aws.yml --env-file .env.aws exec api \
  python3 scripts/seed_demo.py --api-url http://127.0.0.1:8000
```

To reset and restore the vertical scenario later:

```bash
curl -fsS -X POST "$ATLAS_PUBLIC_URL/projects/$PROJECT_ID/demo/reset"
curl -fsS -X POST "$ATLAS_PUBLIC_URL/projects/$PROJECT_ID/demo/vertical-scenario"
```

## Operations

```bash
cd /opt/atlas
alias dc="docker compose -f docker-compose.aws.yml --env-file .env.aws"

dc ps                     # what is running
dc logs -f api            # follow API logs
dc restart api            # restart one service
dc down                   # stop everything (volumes survive)
free -h                   # RAM and swap in use
docker stats --no-stream  # per-container memory
```

Back up the database off the instance before anything judged:

```bash
dc exec -T postgres pg_dump -U atlas atlas | gzip > ~/atlas-backup.sql.gz
```

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `api` restart-loops, logs end abruptly during model load | OOM. Check `free -h` — if swap is 0, bootstrap did not run: `sudo bash /opt/atlas/deploy/bootstrap-ec2.sh`. If swap exists and it still dies, resize to `t3.small`. |
| `/ready` returns 503 with `"database":"error"` | Postgres has not passed its healthcheck yet, or `POSTGRES_PASSWORD` was changed after the volume was created — the existing volume keeps the old password. Check `dc logs postgres`. |
| `/ready` returns 503 with `"qdrant":"error"` | `QDRANT_API_KEY` differs between the `api` and `qdrant` services. Both read the same variable, so this is normally a stale `.env.images` or a partial `up`. |
| Ingestion of a large scanned PDF fails at ~60s | A proxy timeout below `ATLAS_INGESTION_TIMEOUT_SECONDS` (300). The bundled Caddyfile already sets 360s; this appears if you put an ALB or CloudFront in front without raising its idle timeout. |
| `embedding_dimension_mismatch` (409) on upload | The embedding model or dimensions changed against an existing Qdrant collection. Point `ATLAS_QDRANT_COLLECTION` at a new name, or delete the collection and reindex with `--force`. |
| Caddy will not issue a certificate | Port 80 must be open to the world for the ACME challenge, and `ATLAS_SITE_ADDRESS` must resolve to this instance. Check `dc logs caddy`. |
| Disk full | `docker image prune -af`, and check `docker system df`. The deploy prunes automatically, but local `--build` runs accumulate layers. |
| `POST /projects/{id}/copilot` returns 500 on a brand-new instance | Nothing has been ingested yet, so the Qdrant collection does not exist and the query fails with `Collection \`atlas_chunks\` doesn't exist`. Seed the demo (Part 5) or ingest a document first. |
| First query after a deploy takes ~10s | Expected on `t3.micro`: the models are paging in from swap. Only the first one. |
| Deploy job fails `ssh: connect to host *** port 22: Connection timed out` | The security group allows SSH from your IP only, and the runner is not your IP. See the SSH source note in Part 1. The build stage still succeeded, so the images are published. |
| cloud-init failed, no `/opt/atlas`, no swap | Check `sudo tail -50 /var/log/cloud-init-output.log`. A `dnf` conflict on `curl` vs `curl-minimal` is the usual cause - see the user-data note in Part 1. Re-run by hand: `curl -fsSL <raw bootstrap URL> -o /tmp/b.sh && sudo bash /tmp/b.sh`. |
| Copilot answers return `INSUFFICIENT_EVIDENCE` with candidates in the trace | Retrieval worked and generation ran; the claim verifier rejected the answer as ungrounded (`missing_information` says so). This is the evidence guardrail, not a deployment fault - the deterministic engines are unaffected. |

## Security posture

**Authentication is implemented, and the live deployment runs with it on**
(`ATLAS_AUTH_ENABLED=true`, with `JWT_SECRET_KEY` set). Passwords are hashed with `hashlib.scrypt` and session tokens are HMAC-SHA256 signed, both from the standard library. A user is global; `project_members` grants **viewer**, **reviewer** or **admin** per project. Reading needs viewer, mutating needs reviewer, managing members needs admin. A non-member receives **404, not 403**, because a 403 would confirm the project exists.

**It is off by default.** If you stand up an instance without setting
`ATLAS_AUTH_ENABLED`, `project_id` is data scoping rather than authorization and
anyone who can reach the URL can read and upload to every project — acceptable
for a judged demo on a synthetic dataset, not acceptable for real project
content.

Known gaps even with it on: issued tokens cannot be revoked before they expire
(deactivating a user does take effect immediately, since the account is re-read
on every request), there is no password-reset flow, `/auth/login` is not
rate-limited, and `POST /auth/users` is gated on holding admin on *any* project
rather than a platform-wide flag. Concretely, also:

- Keep SSH restricted to your own IP.
- Postgres and Qdrant publish no ports; keep it that way.
- Secrets live only in `/opt/atlas/.env.aws` (mode 600) and in GitHub Actions
  secrets. They are never baked into an image layer or into EC2 user data.
- Rotate `GROQ_API_KEY` and the generated secrets after the event.
- Before this carries anything real, put it behind an authenticated gateway —
  see [ROADMAP.md](ROADMAP.md).

## Teardown

Free-tier hours are per-month, so a forgotten instance starts costing money in
month 13, and a *detached* Elastic IP is billed immediately.

```bash
export AWS_REGION=ap-south-1
./deploy/teardown-aws.sh          # prompts for confirmation
```

It releases the Elastic IP first, terminates the instance, waits, then removes
the security group, key pair, and any orphaned volume. This destroys the
database, the vector collection, and every uploaded document - take a dump
first if you want to keep them.

By hand instead:

1. EC2 → Instances → **Terminate**.
2. EC2 → Elastic IPs → **Release** (a released address cannot be recovered).
3. EC2 → Volumes → delete any volume left in the `available` state.
4. Confirm the next day in Billing → Free tier.
