#!/usr/bin/env bash
#
# One-time preparation of a fresh Amazon Linux 2023 instance.
#
# Paste it into the EC2 launch wizard's "User data" box, or run it over SSH on
# an instance you already launched. It is idempotent - running it twice is safe.
#
# It installs Docker, creates swap, and clones the repository. It deliberately
# does NOT start the stack: .env.aws has to be filled in with real secrets
# first, and those must not be baked into user data (user data is readable from
# the instance metadata service by anything running on the box).

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/mahendraaravind13-creator/project-Atlas.git}"
APP_DIR="${APP_DIR:-/opt/atlas}"
SWAP_GB="${SWAP_GB:-4}"

log() { echo "[bootstrap] $*"; }

# --- swap ------------------------------------------------------------------
# Not optional on a 1 GB free-tier instance. torch plus two MiniLM models is
# roughly 1.0-1.3 GB resident on its own; without swap the kernel OOM-kills the
# API during model load and the container restart-loops. Swap makes it slow on
# the first inference rather than dead.
if [ ! -f /swapfile ]; then
  log "creating ${SWAP_GB}G swapfile"
  dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB * 1024)) status=none
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
  log "swapfile already present"
  swapon --show | grep -q '/swapfile' || swapon /swapfile || true
fi

# Prefer RAM, but use swap rather than dying. The default of 60 thrashes.
if [ ! -f /etc/sysctl.d/99-atlas-swap.conf ]; then
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-atlas-swap.conf
  sysctl -p /etc/sysctl.d/99-atlas-swap.conf >/dev/null
fi

# --- docker ----------------------------------------------------------------
log "installing docker and git"
dnf install -y docker git >/dev/null
systemctl enable --now docker

# The compose plugin is not in the Amazon Linux 2023 repositories, so fetch the
# release binary for this architecture.
COMPOSE_DIR=/usr/local/lib/docker/cli-plugins
if [ ! -x "${COMPOSE_DIR}/docker-compose" ]; then
  log "installing docker compose plugin"
  mkdir -p "$COMPOSE_DIR"
  case "$(uname -m)" in
    x86_64)  COMPOSE_ARCH=x86_64 ;;
    aarch64) COMPOSE_ARCH=aarch64 ;;
    *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
  esac
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-${COMPOSE_ARCH}" \
    -o "${COMPOSE_DIR}/docker-compose"
  chmod +x "${COMPOSE_DIR}/docker-compose"
fi

# Lets the deploy run without sudo. Requires a new login session to take effect.
usermod -aG docker ec2-user || true

# Container logs are the only diagnostic on this box; uncapped they will fill a
# 30 GB volume and take Postgres down with them.
if [ ! -f /etc/docker/daemon.json ]; then
  log "capping container log size"
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
  systemctl restart docker
fi

# --- repository ------------------------------------------------------------
if [ ! -d "${APP_DIR}/.git" ]; then
  log "cloning ${REPO_URL} into ${APP_DIR}"
  git clone "$REPO_URL" "$APP_DIR"
else
  log "repository already present at ${APP_DIR}"
fi
chown -R ec2-user:ec2-user "$APP_DIR"

if [ ! -f "${APP_DIR}/.env.aws" ]; then
  install -o ec2-user -g ec2-user -m 600 \
    "${APP_DIR}/deploy/env.aws.example" "${APP_DIR}/.env.aws"
  log "created ${APP_DIR}/.env.aws from the template - FILL IT IN"
fi

cat <<EOF

[bootstrap] done.

Next, on the instance:
  1. edit ${APP_DIR}/.env.aws and set ATLAS_PUBLIC_URL, POSTGRES_PASSWORD,
     QDRANT_API_KEY and GROQ_API_KEY
       openssl rand -hex 24     # for the two generated secrets
  2. cd ${APP_DIR}
     docker compose -f docker-compose.aws.yml --env-file .env.aws up -d --build
  3. curl -fsS localhost/health && curl -fsS localhost/ready

Full runbook: docs/AWS_DEPLOY.md
EOF
