#!/usr/bin/env bash
#
# Provision the AWS side of the single-instance deployment.
#
# Creates (or reuses) a key pair, a security group, a free-tier EC2 instance
# with a 30 GB root volume, and an Elastic IP. Everything it makes is tagged
# Project=atlas so teardown-aws.sh can find it again.
#
#   export AWS_REGION=ap-south-1
#   export REPO_URL=https://github.com/<you>/ET_HACKTON_MAIN.git
#   ./deploy/provision-aws.sh
#
# Requires: aws CLI v2 with working credentials (`aws sts get-caller-identity`).
#
# It is idempotent - every step checks for an existing resource first, so a
# re-run after a partial failure continues rather than duplicating anything.
# It does NOT put secrets on the instance; user data is world-readable from the
# instance metadata service, so .env.aws is filled in over SSH afterwards.

set -euo pipefail

NAME="${NAME:-atlas}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
VOLUME_GB="${VOLUME_GB:-30}"
REPO_URL="${REPO_URL:-}"
KEY_FILE="${KEY_FILE:-./${NAME}.pem}"

die() { echo "error: $*" >&2; exit 1; }
log() { echo "==> $*"; }

command -v aws >/dev/null || die "aws CLI not found on PATH"
[ -n "$REGION" ] || die "set AWS_REGION (e.g. export AWS_REGION=ap-south-1)"
[ -n "$REPO_URL" ] || die "set REPO_URL to your git remote (the instance clones it)"

aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no working AWS credentials - run 'aws configure' first"

export AWS_DEFAULT_REGION="$REGION"
log "region ${REGION}, account $(aws sts get-caller-identity --query Account --output text)"

# --- warn if this instance type is not free-tier eligible ------------------
if [ "$INSTANCE_TYPE" != "t3.micro" ] && [ "$INSTANCE_TYPE" != "t2.micro" ]; then
  echo "warning: ${INSTANCE_TYPE} is probably NOT free-tier eligible." >&2
  echo "         t3.micro is the free-tier type. Continuing in 5s; Ctrl-C to stop." >&2
  sleep 5
fi

# --- default VPC and a subnet ---------------------------------------------
VPC_ID=$(aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
[ "$VPC_ID" != "None" ] || die "no default VPC in ${REGION}; create one (VPC console -> Actions -> Create default VPC)"

SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
  --query 'Subnets[0].SubnetId' --output text)
[ "$SUBNET_ID" != "None" ] || die "no default subnet found in ${VPC_ID}"
log "vpc ${VPC_ID}, subnet ${SUBNET_ID}"

# --- key pair --------------------------------------------------------------
# A key pair's private half is only ever returned at creation time. If the key
# exists in AWS but the .pem is gone locally, it is unusable - say so rather
# than launching an instance nobody can log into.
if aws ec2 describe-key-pairs --key-names "$NAME" >/dev/null 2>&1; then
  if [ -f "$KEY_FILE" ]; then
    log "key pair ${NAME} exists, using ${KEY_FILE}"
  else
    die "key pair ${NAME} exists in AWS but ${KEY_FILE} is missing.
     AWS only returns the private key once. Either restore the file, or:
       aws ec2 delete-key-pair --key-name ${NAME}
     and re-run to create a fresh one."
  fi
else
  log "creating key pair ${NAME}"
  aws ec2 create-key-pair \
    --key-name "$NAME" \
    --key-type ed25519 \
    --tag-specifications "ResourceType=key-pair,Tags=[{Key=Project,Value=atlas}]" \
    --query KeyMaterial --output text > "$KEY_FILE"
  chmod 400 "$KEY_FILE"
  log "wrote ${KEY_FILE} - back this up, AWS will not show it again"
fi

# --- security group --------------------------------------------------------
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${NAME}-sg" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  log "creating security group ${NAME}-sg"
  SG_ID=$(aws ec2 create-security-group \
    --group-name "${NAME}-sg" \
    --description "Project Atlas single-instance deployment" \
    --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=security-group,Tags=[{Key=Project,Value=atlas}]" \
    --query GroupId --output text)
else
  log "security group ${SG_ID} exists"
fi

# SSH is restricted to the address running this script. The application has no
# authentication of its own, so a world-open port 22 would be the whole box.
MY_IP=$(curl -fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]' || true)
if [ -n "$MY_IP" ]; then
  log "authorising SSH from ${MY_IP}/32"
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${MY_IP}/32,Description=admin}]" \
    >/dev/null 2>&1 || log "  (SSH rule already present)"
else
  echo "warning: could not determine your public IP; add the SSH rule manually" >&2
fi

# 80 must be open to the world for the Let's Encrypt HTTP-01 challenge.
for port in 80 443; do
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=${port},ToPort=${port},IpRanges=[{CidrIp=0.0.0.0/0,Description=public}]" \
    >/dev/null 2>&1 && log "authorised port ${port}" || log "  (port ${port} rule already present)"
done

# --- AMI -------------------------------------------------------------------
# Resolved from the SSM public parameter rather than hardcoded: AMI IDs are
# per-region and change with every Amazon Linux release.
AMI_ID=$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value --output text)
log "AMI ${AMI_ID} (Amazon Linux 2023)"

# --- instance --------------------------------------------------------------
EXISTING=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${NAME}" \
            "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "None")

if [ "$EXISTING" != "None" ] && [ -n "$EXISTING" ]; then
  INSTANCE_ID="$EXISTING"
  log "instance ${INSTANCE_ID} already exists, reusing it"
else
  USER_DATA=$(mktemp)
  # Bake REPO_URL into the copy of the bootstrap script that user data carries,
  # so the instance clones the right repository without further editing.
  sed "s|^REPO_URL=.*|REPO_URL=\"\${REPO_URL:-${REPO_URL}}\"|" \
    "$(dirname "$0")/bootstrap-ec2.sh" > "$USER_DATA"

  log "launching ${INSTANCE_TYPE} with a ${VOLUME_GB} GB gp3 root volume"
  INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$NAME" \
    --security-group-ids "$SG_ID" \
    --subnet-id "$SUBNET_ID" \
    --associate-public-ip-address \
    --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":${VOLUME_GB},\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true,\"Encrypted\":true}}]" \
    --user-data "file://${USER_DATA}" \
    --metadata-options "HttpTokens=required" \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=${NAME}},{Key=Project,Value=atlas}]" \
      "ResourceType=volume,Tags=[{Key=Project,Value=atlas}]" \
    --query 'Instances[0].InstanceId' --output text)
  rm -f "$USER_DATA"
  log "launched ${INSTANCE_ID}"
fi

log "waiting for ${INSTANCE_ID} to reach running state"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# --- Elastic IP ------------------------------------------------------------
# Without one the public IP changes on every stop/start, which breaks the TLS
# hostname and the EC2_HOST secret. Free while associated with a running
# instance; billed if left allocated and detached.
CURRENT_EIP=$(aws ec2 describe-addresses \
  --filters "Name=instance-id,Values=${INSTANCE_ID}" \
  --query 'Addresses[0].PublicIp' --output text 2>/dev/null || echo "None")

if [ "$CURRENT_EIP" != "None" ] && [ -n "$CURRENT_EIP" ]; then
  PUBLIC_IP="$CURRENT_EIP"
  log "elastic IP ${PUBLIC_IP} already associated"
else
  UNUSED=$(aws ec2 describe-addresses \
    --filters "Name=tag:Project,Values=atlas" \
    --query 'Addresses[?AssociationId==null] | [0].AllocationId' --output text 2>/dev/null || echo "None")
  if [ "$UNUSED" != "None" ] && [ -n "$UNUSED" ]; then
    ALLOC_ID="$UNUSED"
    log "reusing unassociated elastic IP ${ALLOC_ID}"
  else
    log "allocating an elastic IP"
    ALLOC_ID=$(aws ec2 allocate-address --domain vpc \
      --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Project,Value=atlas}]" \
      --query AllocationId --output text)
  fi
  aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" >/dev/null
  PUBLIC_IP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC_ID" \
    --query 'Addresses[0].PublicIp' --output text)
  log "associated ${PUBLIC_IP}"
fi

SSLIP_HOST="$(echo "$PUBLIC_IP" | tr '.' '-').sslip.io"

cat <<EOF

────────────────────────────────────────────────────────────────────
  Instance   ${INSTANCE_ID}   (${INSTANCE_TYPE}, ${REGION})
  Public IP  ${PUBLIC_IP}
  HTTPS host ${SSLIP_HOST}
  SSH key    ${KEY_FILE}
────────────────────────────────────────────────────────────────────

The bootstrap script is still running on first boot (Docker install, 4 GB
swap, git clone). Give it 2-3 minutes, then:

  ssh -i ${KEY_FILE} ec2-user@${PUBLIC_IP}

  # confirm bootstrap finished - expect ~4 GB swap and a docker version
  free -h && docker compose version

  cd /opt/atlas
  openssl rand -hex 24   # POSTGRES_PASSWORD
  openssl rand -hex 24   # QDRANT_API_KEY
  nano .env.aws          # set the two above, GROQ_API_KEY, and:
                         #   ATLAS_SITE_ADDRESS=${SSLIP_HOST}
                         #   ATLAS_PUBLIC_URL=https://${SSLIP_HOST}

  docker compose -f docker-compose.aws.yml --env-file .env.aws up -d --build
  curl -fsS localhost/health && curl -fsS localhost/ready

Then wire up push-to-deploy with these GitHub Actions secrets:

  EC2_HOST = ${PUBLIC_IP}
  EC2_USER = ec2-user
  EC2_SSH_KEY = contents of ${KEY_FILE}

Full runbook: docs/AWS_DEPLOY.md
Teardown:     ./deploy/teardown-aws.sh
EOF
