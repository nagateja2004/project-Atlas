#!/usr/bin/env bash
#
# Remove everything provision-aws.sh created.
#
#   export AWS_REGION=ap-south-1
#   ./deploy/teardown-aws.sh
#
# Worth actually running when the demo is over: free-tier hours are monthly, so
# a forgotten instance starts billing in month 13, and an Elastic IP that is
# allocated but NOT associated is billed immediately.
#
# This destroys data. The database, the Qdrant collection, and every uploaded
# document live on the instance's EBS volume and are deleted with it. Take a
# dump first if you want to keep anything:
#   ssh -i atlas.pem ec2-user@<ip> \
#     'cd /opt/atlas && docker compose -f docker-compose.aws.yml --env-file .env.aws \
#      exec -T postgres pg_dump -U atlas atlas' | gzip > atlas-backup.sql.gz

set -euo pipefail

NAME="${NAME:-atlas}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"

die() { echo "error: $*" >&2; exit 1; }
log() { echo "==> $*"; }

command -v aws >/dev/null || die "aws CLI not found on PATH"
[ -n "$REGION" ] || die "set AWS_REGION"
aws sts get-caller-identity >/dev/null 2>&1 || die "no working AWS credentials"
export AWS_DEFAULT_REGION="$REGION"

INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${NAME}" \
            "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "None")

echo
echo "About to delete, in region ${REGION}:"
echo "  instance       ${INSTANCE_ID}"
echo "  security group ${NAME}-sg"
echo "  key pair       ${NAME}"
echo "  elastic IPs    tagged Project=atlas"
echo
echo "The EBS volume goes with the instance: database, vectors and uploaded"
echo "documents are destroyed and are NOT recoverable."
echo
printf 'Type the word DELETE to continue: '
read -r CONFIRM
[ "$CONFIRM" = "DELETE" ] || die "aborted (nothing was changed)"

# --- Elastic IPs -----------------------------------------------------------
# Released before the instance is terminated: a release on an address that is
# still associated is rejected in some cases, and disassociating first is
# always safe.
for ALLOC in $(aws ec2 describe-addresses --filters "Name=tag:Project,Values=atlas" \
                 --query 'Addresses[].AllocationId' --output text 2>/dev/null || true); do
  [ -n "$ALLOC" ] || continue
  ASSOC=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" \
    --query 'Addresses[0].AssociationId' --output text 2>/dev/null || echo "None")
  if [ "$ASSOC" != "None" ] && [ -n "$ASSOC" ]; then
    log "disassociating ${ALLOC}"
    aws ec2 disassociate-address --association-id "$ASSOC" >/dev/null || true
  fi
  log "releasing ${ALLOC}"
  aws ec2 release-address --allocation-id "$ALLOC" >/dev/null || true
done

# --- instance --------------------------------------------------------------
if [ "$INSTANCE_ID" != "None" ] && [ -n "$INSTANCE_ID" ]; then
  log "terminating ${INSTANCE_ID}"
  aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
  log "waiting for termination (the security group cannot be deleted until then)"
  aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
fi

# --- security group --------------------------------------------------------
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${NAME}-sg" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  log "deleting security group ${SG_ID}"
  aws ec2 delete-security-group --group-id "$SG_ID" >/dev/null || \
    echo "  could not delete ${SG_ID} - something may still reference it" >&2
fi

# --- key pair --------------------------------------------------------------
if aws ec2 describe-key-pairs --key-names "$NAME" >/dev/null 2>&1; then
  log "deleting key pair ${NAME}"
  aws ec2 delete-key-pair --key-name "$NAME" >/dev/null
fi

# --- orphaned volumes ------------------------------------------------------
for VOL in $(aws ec2 describe-volumes \
               --filters "Name=tag:Project,Values=atlas" "Name=status,Values=available" \
               --query 'Volumes[].VolumeId' --output text 2>/dev/null || true); do
  [ -n "$VOL" ] || continue
  log "deleting orphaned volume ${VOL}"
  aws ec2 delete-volume --volume-id "$VOL" >/dev/null || true
done

cat <<EOF

Teardown complete.

Two things this script does NOT touch:
  - the local ${NAME}.pem file (delete it yourself if you want)
  - container images in ghcr.io (GitHub -> Packages, if you want them gone)

Check Billing -> Free tier tomorrow to confirm nothing is still accruing.
EOF
