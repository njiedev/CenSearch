#!/usr/bin/env bash
# Owner-triggered only. Recognizable research fixtures must never leave this machine.
set -euo pipefail
backend_root=$(cd "$(dirname "$0")/.." && pwd)
[[ $# == 1 ]] || { echo 'Usage: deploy/seed_remote.sh <photo-folder>' >&2; exit 1; }
python3 "$backend_root/deploy/guard_photos.py" "$1"
ssh_key=${SSH_KEY:-$HOME/.ssh/id_ed25519}
label=${LINODE_LABEL:-likeness-guard}
server=${LINODE_HOST:-}
if [[ -z "$server" ]]; then
    server=$(linode-cli linodes list --label "$label" --text --no-headers --format ipv4)
    [[ "$server" != *$'\n'* ]] || { echo 'Multiple matching servers' >&2; exit 1; }
    server=${server%% *}
fi
[[ "$server" =~ ^[A-Za-z0-9.-]+$ ]] || { echo 'Set LINODE_HOST to the deployed server' >&2; exit 1; }
ssh_options=(-i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes)
bundle=$(mktemp "${TMPDIR:-/tmp}/likeness-owner-photos.XXXXXX")
trap 'rm -f "$bundle"' EXIT
chmod 600 "$bundle"
COPYFILE_DISABLE=1 tar --exclude='.DS_Store' -czf "$bundle" -C "$1" .
ssh "${ssh_options[@]}" "root@$server" 'install -d -m 0700 /opt/censearch/owner-photos'
scp "${ssh_options[@]}" -q "$bundle" "root@$server:/opt/censearch/owner-photos/photos.tar.gz"
ssh "${ssh_options[@]}" "root@$server" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /opt/censearch
photo_run=$(date +%s)
install -d -m 0700 "owner-photos/$photo_run"
tar -xzf owner-photos/photos.tar.gz -C "owner-photos/$photo_run"
rm owner-photos/photos.tar.gz
# Generate in an empty staging directory. Publish only after successful seeding.
docker compose -f deploy/compose.yaml run --rm \
  -v "/opt/censearch/owner-photos/$photo_run:/owner-photos:ro" \
  --entrypoint /bin/sh mockweb -c \
  'uv run --no-sync python -m mockweb.seed --photos /owner-photos --output /tmp/planted --base-port 8811 && cp -a /tmp/planted/. /mock-sites/'
docker compose -f deploy/compose.yaml restart mockweb >/dev/null
echo 'Owner photo planting completed; mock web service restarted.'
REMOTE
