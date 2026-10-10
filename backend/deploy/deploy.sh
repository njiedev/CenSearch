#!/usr/bin/env bash
# Adapted from akamai-developers/akamai-workshop-hackmidwest/scripts/deploy_linode.sh.
# Run only when the owner explicitly requests cloud deployment.
set -euo pipefail
backend_root=$(cd "$(dirname "$0")/.." && pwd)
ssh_key=${SSH_KEY:-$HOME/.ssh/id_ed25519}
region=${LINODE_REGION:-us-ord}
label=${LINODE_LABEL:-likeness-guard}
firewall_label="${label}-web"
for executable in linode-cli ssh scp tar openssl python3; do
    command -v "$executable" >/dev/null || { echo "Missing $executable" >&2; exit 1; }
done
[[ -f "$ssh_key.pub" && -f "$backend_root/.env" ]] || { echo 'Need an SSH key and backend/.env' >&2; exit 1; }
# Parse only for presence. Never source .env as shell code or display credentials.
python3 - "$backend_root/.env" <<'PY'
import sys
from pathlib import Path
values = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip("\"'")
if not values.get('APP_PASSWORD_HASH', '').startswith('$2'):
    raise SystemExit('Set APP_PASSWORD_HASH to a Caddy bcrypt hash in backend/.env')
PY
ssh_options=(-i "$ssh_key" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes)
wait_for() {
    local deadline=$((SECONDS + $1))
    shift
    until "$@"; do
        (( SECONDS < deadline )) || { echo 'Timed out' >&2; return 1; }
        sleep 5
    done
}
# Reuse only one uniquely labelled resource; always restore restrictive rules.
firewall_id=$(linode-cli firewalls list --label "$firewall_label" --text --no-headers --format id)
[[ "$firewall_id" != *$'\n'* ]] || { echo 'Multiple matching firewalls' >&2; exit 1; }
inbound='[{"label":"ssh-https-http","action":"ACCEPT","protocol":"TCP","ports":"22,80,443","addresses":{"ipv4":["0.0.0.0/0"],"ipv6":["::/0"]}}]'
if [[ -z "$firewall_id" ]]; then
    firewall_id=$(linode-cli firewalls create --label "$firewall_label" --rules.inbound_policy DROP \
        --rules.outbound_policy ACCEPT --rules.inbound "$inbound" --text --no-headers --format id)
else
    linode-cli firewalls rules-update "$firewall_id" --inbound_policy DROP --outbound_policy ACCEPT --inbound "$inbound" >/dev/null
fi
linode_id=$(linode-cli linodes list --label "$label" --text --no-headers --format id)
[[ "$linode_id" != *$'\n'* ]] || { echo 'Multiple matching Linodes' >&2; exit 1; }
if [[ -z "$linode_id" ]]; then
    user_data=$(base64 < "$backend_root/deploy/cloud-init.yaml" | tr -d '\n')
    linode_id=$(linode-cli linodes create --label "$label" --region "$region" --type g6-standard-2 \
        --image linode/ubuntu24.04 --root_pass "$(openssl rand -base64 32)" \
        --authorized_keys "$(cat "$ssh_key.pub")" --firewall_id "$firewall_id" \
        --metadata.user_data "$user_data" --text --no-headers --format id)
else
    # Ensure the existing machine is attached to this firewall.
    devices=$(linode-cli firewalls devices-list "$firewall_id" --json)
    if ! python3 -c 'import json,sys; rows=json.load(sys.stdin); sys.exit(not any(str(x.get("entity",{}).get("id")) == sys.argv[1] for x in rows))' "$linode_id" <<< "$devices"; then
        linode-cli firewalls device-create "$firewall_id" --id "$linode_id" --type linode >/dev/null
    fi
fi
ip=$(linode-cli linodes view "$linode_id" --text --no-headers --format ipv4)
ip=${ip%% *}
[[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid IPv4 response' >&2; exit 1; }
wait_for 600 ssh "${ssh_options[@]}" "root@$ip" true
ssh "${ssh_options[@]}" "root@$ip" 'cloud-init status --wait && install -d -m 0700 /opt/censearch'
# Explicit allowlist excludes all local photos, fixtures, data and models.
bundle=$(mktemp "${TMPDIR:-/tmp}/likeness-deploy.XXXXXX")
remote_env=$(mktemp "${TMPDIR:-/tmp}/likeness-env.XXXXXX")
trap 'rm -f "$bundle" "$remote_env"' EXIT
chmod 600 "$remote_env"
python3 - "$backend_root/.env" "$remote_env" "$ip" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text().splitlines()
lines = [line for line in lines if not line.startswith('APP_HOST=')]
lines.append('APP_HOST=' + sys.argv[3] + '.sslip.io')
Path(sys.argv[2]).write_text('\n'.join(lines) + '\n')
PY
COPYFILE_DISABLE=1 tar --exclude='__pycache__' --exclude='*.pyc' --exclude='node_modules' --exclude='dist' --exclude='*.md' \
    -czf "$bundle" -C "$backend_root" pyproject.toml uv.lock .python-version .dockerignore \
    censearch mockweb scripts/setup_models.py reports/calibration.json demo-ui deploy
scp "${ssh_options[@]}" -q "$bundle" "root@$ip:/opt/censearch/code.tar.gz"
scp "${ssh_options[@]}" -q "$remote_env" "root@$ip:/opt/censearch/.env.next"
# Preserve prior remote Object Storage credentials on repeat deploys.
ssh "${ssh_options[@]}" "root@$ip" 'python3 -' <<'PYREMOTE'
from pathlib import Path
root = Path('/opt/censearch')
current = root / '.env'
incoming = root / '.env.next'
lines = incoming.read_text().splitlines()
if current.exists():
    saved = [line for line in current.read_text().splitlines() if line.startswith('OBJ_')]
    if saved:
        lines = [line for line in lines if not line.startswith('OBJ_')] + saved
incoming.write_text('\n'.join(lines) + '\n')
incoming.chmod(0o600)
incoming.replace(current)
PYREMOTE
python3 "$backend_root/deploy/provision_storage.py" --host "root@$ip" --ssh-key "$ssh_key" \
    --region "$region" --bucket "${OBJ_BUCKET_LABEL:-${label}-evidence}"
ssh "${ssh_options[@]}" "root@$ip" 'cd /opt/censearch && tar -xzf code.tar.gz && docker compose -f deploy/compose.yaml up -d --build > deploy.log 2>&1'
echo "Started deployment at https://$ip.sslip.io (username demo). Inspect /opt/censearch/deploy.log if startup failed."
echo 'Mock sites start empty. Seed them only with owner-approved photos copied separately; local fixtures were not uploaded.'
