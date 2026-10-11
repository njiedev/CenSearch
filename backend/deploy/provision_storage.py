"""Owner-triggered Linode CLI provisioning. New credentials live only in the remote .env.

Current CLI contract: https://techdocs.akamai.com/cloud-computing/docs/using-the-linode-cli-with-object-storage
Never echo CLI output: keys-create returns a secret only once.
"""

import argparse
import configparser
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

READ_ENV = """import json
from pathlib import Path
values = {}
for line in Path('/opt/censearch/.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        if key.startswith('OBJ_'):
            values[key] = value.strip().strip(chr(34) + chr(39))
print(json.dumps(values))
"""
WRITE_ENV = """import json, os, sys
from pathlib import Path
values = json.load(sys.stdin)
p = Path('/opt/censearch/.env')
lines = [line for line in p.read_text().splitlines() if not line.startswith('OBJ_')]
lines.extend(key + '=' + chr(39) + value + chr(39) for key, value in values.items())
temporary = p.with_suffix('.pending')
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write('\\n'.join(lines) + '\\n')
temporary.replace(p)
"""


def command(args, input=None):
    result = subprocess.run(args, input=input, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Provisioning command failed (output withheld because it may contain credentials)")
    return result.stdout


def cli(*args):
    return json.loads(command(["linode-cli", "object-storage", *args, "--json"]))


def api_token():
    token = os.environ.get("LINODE_CLI_TOKEN")
    if token:
        return token
    config = configparser.ConfigParser()
    config.read(Path.home() / ".config/linode-cli")
    user = config.get("DEFAULT", "default-user", fallback=None)
    token = config.get(user, "token", fallback=None) if user else None
    if not token:
        raise RuntimeError("No Linode API token found; run linode-cli configure")
    return token


def create_bucket(label, region):
    # linode-cli 5.69 dropped the bucket actions, so this one call uses the REST API.
    # Creating a bucket that this account already owns returns the existing bucket.
    request = urllib.request.Request(
        "https://api.linode.com/v4/object-storage/buckets",
        data=json.dumps({"label": label, "region": region}).encode(),
        headers={"Authorization": "Bearer " + api_token(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        reasons = [item.get("reason") for item in json.load(error).get("errors", [])]
        raise RuntimeError(f"Bucket creation failed ({error.code}): {reasons}") from None


def single(value):
    return value[0] if isinstance(value, list) else value


def main():
    import shlex

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--region", default="us-ord")
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args()
    ssh = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "BatchMode=yes",
        args.host,
    ]
    existing = json.loads(command([*ssh, "python3 -c " + shlex.quote(READ_ENV)]))
    bucket = create_bucket(args.bucket, args.region)
    endpoint = bucket.get("s3_endpoint")
    if not endpoint:
        raise RuntimeError("Bucket response omitted s3_endpoint; refusing to guess it")
    label = args.bucket + "-app"
    scope = [{"region": args.region, "bucket_name": args.bucket, "permissions": "read_write"}]
    keys = cli("keys-list")
    matches = [key for key in keys if key.get("label") == label]
    if len(matches) > 1:
        raise RuntimeError("Multiple keys with the application label; reconcile them before deploying")
    if matches:
        key = matches[0]
        if (
            existing.get("OBJ_BUCKET") != args.bucket
            or existing.get("OBJ_ACCESS_KEY") != key["access_key"]
            or not existing.get("OBJ_SECRET_KEY")
            or not key.get("limited")
        ):
            raise RuntimeError(
                "Existing key cannot be safely recovered; preserve the remote .env or reconcile the key"
            )
        permissions = key.get("bucket_access", [])
        if len(permissions) != 1 or any(permissions[0].get(k) != v for k, v in scope[0].items()):
            raise RuntimeError("Existing application key is not scoped exclusively to this bucket")
        secret = existing["OBJ_SECRET_KEY"]
    else:
        key = single(cli("keys-create", "--label", label, "--bucket_access", json.dumps(scope)))
        secret = key["secret_key"]
    values = {
        "OBJ_ENDPOINT": "https://" + endpoint.removeprefix("https://"),
        "OBJ_BUCKET": args.bucket,
        "OBJ_ACCESS_KEY": key["access_key"],
        "OBJ_SECRET_KEY": secret,
    }
    command([*ssh, "python3 -c " + shlex.quote(WRITE_ENV)], input=json.dumps(values))
    print("Object Storage bucket and scoped key configured in remote .env; no credentials displayed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error)) from None
