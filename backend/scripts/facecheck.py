"""Account check or explicitly authorized photo FaceCheck trial; no servers or notice delivery."""

import argparse
import json
import os
from pathlib import Path
import sys

import httpx

from censearch.config import Settings
from censearch.facecheck import FaceCheckClient, FaceCheckError


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--info", action="store_true", help="Check auth and balance; no upload")
    action.add_argument("--image", type=Path, help="Local authorized photo, never a fixture")
    action.add_argument("--resume", help="Check an existing search ID without submitting again")
    parser.add_argument(
        "--consent-upload",
        action="store_true",
        help="Confirm authorization to send this selected photo to FaceCheck",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run a real search (3 credits); default is free testing mode",
    )
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument(
        "--output",
        type=Path,
        help="Private JSON output; defaults to ignored data/facecheck/latest.json",
    )
    args = parser.parse_args()
    if args.image and not args.consent_upload:
        parser.error("--image requires --consent-upload for this selected photo")
    if not 1 <= args.wait_seconds <= 600:
        parser.error("--wait-seconds must be between 1 and 600")
    settings = Settings()
    output = args.output or settings.data_dir / "facecheck/latest.json"
    try:
        with httpx.Client(trust_env=False, follow_redirects=False) as http:
            client = FaceCheckClient(settings, http)
            info = client.info()
            print(json.dumps(info), flush=True)
            if args.info:
                return 0
            if info.get("is_online") is False:
                raise FaceCheckError("FaceCheck is currently offline")
            if args.live and not args.resume and info["remaining_credits"] < 3:
                raise FaceCheckError("A live search needs at least 3 credits")
            print(
                "Live search · 3 credits"
                if args.live
                else "Testing mode · free; results are not meaningful",
                flush=True,
            )
            search_id = args.resume
            if args.image:
                with args.image.expanduser().open("rb") as stream:
                    payload = stream.read(settings.upload_limit_bytes + 1)
                search_id = client.upload(payload, upload_consent=args.consent_upload)
                # Persist before submitting so an interrupted search can be recovered.
                save(
                    output,
                    {"id_search": search_id, "status": "uploaded", "testing_mode": not args.live},
                )
            print(f"Search ID: {search_id}", flush=True)
            result = client.search(
                search_id,
                live=args.live,
                resume=bool(args.resume),
                wait_seconds=args.wait_seconds,
                progress=lambda value: print(
                    f"Progress: {value if value is not None else 'waiting'}", flush=True
                ),
            )
            save(output, result)
            print(f"{result['status']}: {len(result['items'])} possible matches. Saved: {output}")
            if result["status"] == "pending":
                print("Use --resume with this search ID to check again; do not re-upload.")
                return 2
            print(json.dumps(client.info()), flush=True)
            return 0
    except (FaceCheckError, ValueError, OSError) as error:
        print(f"FaceCheck trial failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
