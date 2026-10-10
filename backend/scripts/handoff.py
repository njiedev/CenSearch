"""Regenerate integration handoff from actual round 1 and round 2 HTTP captures."""

import argparse
import json
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[1]
GUIDE = """# Frontend agent brief: Likeness Guard round 2

The existing frontend is untouched. Connect it to the backend when its owner asks.
Read openapi.json for parameter contracts and backend/demo-ui/src/ for a working React console.
Examples below came from running FastAPI and browser sessions. IDs, hashes and timestamps vary.
All example photos and assertions are local development fixtures, not actual ownership or consent claims.

## Local startup

For the stay-open local dataset demo, run `make demo`. It seeds, enrols a development fixture,
runs Find, opens the default browser and waits for Ctrl-C. Data stays under data/demo-*.
Override photos with `make demo PHOTOS="/path/to/local-photos"`.
For occupied ports use `make demo API_PORT=8290 BASE_PORT=8911`.
The Makefile default is the owner's local LFW seed folder; it is never a deployment input.
Scripted checks are `make e2e` and `make e2e-round2`, with the same PHOTOS/API_PORT/BASE_PORT overrides.

```sh
cd backend
make setup
cp .env.example .env
# Configure secrets locally. Do not paste them in chat.
make api
```

The API and built console share http://127.0.0.1:8190; API paths start with /api.
Interactive API documentation is at /docs. Console development uses 5183. Port 5173 stays with the owner.
Use a Vite /api proxy to 8190 from the existing frontend; CORS is not enabled.
Dependencies, models and Chromium install through make setup. No face dataset is downloaded.

```sh
make seed PHOTOS="/path/to/owner-photos" MOCK_ROOT="data/my-sites"
make mock MOCK_ROOT="data/my-sites"
```

Photo layout: <person>/reference/, originals/, wild/, optional distractors/ at the top level.
Supply at least one original and three different wild photos. Seed output must initially be empty.
Mocks: pixboard 8811, friendlink 8812, localnews 8813, shadygallery 8814, host 8815,
search 8816, registry 8817, SMTP 8818. The acceptance-only refusal site uses base port + 8.
.env.example includes local SMTP, RDAP and search adapters. They apply only to loopback lookups.
Do not send face-bearing debug screenshots to a model-backed image viewer.
Product code never reads mock state or ground truth. The API communicates through HTTP/SMTP only.

```sh
uv run pytest
uv run python scripts/e2e.py --photos "/path/to/local-photos" --browser
uv run python scripts/e2e_round2.py --photos "/path/to/local-photos" --browser
```

Both scripts stop their child processes and browsers in finally. They support --api-port and --base-port
for occupied ports. Their output is in data/e2e-* and data/round2-*; screenshots and cleanup records live there.
Fixture names/files are replaced with neutral names in the temporary copy. Never upload development fixtures.
Round 2 disables the model and remote storage in its fixture child; simulated-provider tests run only in pytest.

## Enrol and find

1. GET /api/health and /api/people. Face models must be loaded before enrolment or crawl.
2. POST /api/people with FormData: name, consent, repeated references files; optional originals plus ownership.
   Do not manually set multipart Content-Type. Webcam canvas blobs work as File values.
   Only explicitly local fixture runs set development_fixture=true. Examine every photo validation result.
3. Refresh /api/people. DELETE /api/people/{id} deletes identity-owned data, including round 2 records/evidence.
4. POST /api/crawls with seeds, rendered, delay and max_pages. Poll /api/crawls/{id} until terminal status.
   Read errors/metrics; partial, failed and interrupted runs are not successes. GET /api/scans shows scan metadata.
5. GET /api/cases, optionally filtered by person_id/run_id. Use matched_image_url for the retained image.
   Similarity scores are not confidence percentages. Different-photo face matches cannot support copyright.

## Decide

1. GET /api/cases/{id}/workflow for questions, answers, revision, decisions, evidence and timeline.
2. POST /api/cases/{id}/description before questions. Advisory only; model_not_configured is a normal state.
   The flow continues without it. A model receives only page text and URLs, never pictures or personal answers.
3. Render questions as unanswered/yes/no. Each answer stores question, value, answered_by and answered_at.
   Never preselect yes. Additional statements are required for notice templates; they are also individual records.
4. POST /api/cases/{id}/answers with answered_by, answers and contact. This replaces the whole answer set.
   Omitted values become null. work_description/explanation are user text. Save contact
name/email/address/phone/signature.
   New saves increment revision and invalidate old approvals. Answers freeze after a delivery attempt.
5. GET /api/cases/{id}/route shows route, rule_id, version and exact inputs. No model selects the route.
   Routes: copyright_notice, impersonation_report, intimate_image_report, privacy_request, leave_alone, hold_for_review.
   Precedence: authorized/legitimate, identity hold, intimate, impersonation, owned verified copy,
   unresolved copy hold, explicit privacy, otherwise leave alone. Leave/hold cannot draft or send.
6. POST /api/cases/{id}/evidence captures a full-page screenshot and bundle before drafting.
   GET /api/cases/{id}/screenshot displays it. Evidence records hashes, headers, source URLs and timestamps.
   Evidence freezes after a notice exists. Stored identity files are private, with no-store image responses.

## Research, approve and send

1. POST /api/cases/{id}/recipients runs Strands when configured, otherwise deterministic_baseline.
   Provider/parse/tool provenance failure also falls back, with model_status=model_error and agent_attempt retained.
   Display source, model_status, tool_calls, requests, recipients and evidence. Do not label the baseline an agent.
   Tool traces return after completion; there is no live SSE stream. Strands is capped at 12 model calls.
2. Choose a returned recipient ID for next_rung (site, host or search). Contacts include rank, channel,
   address, endpoint and evidence. RDAP may identify a CDN serving network; it does not establish hidden origin hosting.
3. POST /approve-draft with approved_by, current revision and rung. This permits preparation only.
4. POST /draft with recipient_id and rung. A successful response has id, payload.body, sha256 and recipient.
   GET /draft retrieves the latest request. Templates are fixed; copyright refuses any missing required statement.
5. Show the full body, recipient and rung. POST /approve with notice_id, sha256 and approved_by.
   This approval binds the exact payload including recipient, facts, template and evidence bundle hash.
6. POST /send only after approval. Duplicate sends and superseded approvals are refused.
   Mail/form adapters use literal loopback or resolved localhost, with redirects/proxies disabled.
   Real recipients are manual_email/manual_web: stop at the draft and named recipient; the person sends it themselves.
   Never enable LIKENESS_ALLOW_EXTERNAL_DELIVERY for this project.

## Verify and follow up

POST /api/cases/{id}/verify re-fetches page/image. Outcomes: removed, still_present, replaced, blocked,
unreachable, uncertain. A timeout, block or acknowledgement never means removal. Uncertain changed bytes abstain.
404/410 counts as removed only with a reachable origin and compatible page status.
Search delisting is a separate delivery outcome; it never changes source_removed to true.

GET /workflow returns the timeline, deliveries, checks and next_rung. Only silence and a still-present source
past the default 48-hour deadline makes the next rung available. The scheduler never sends automatically.
A fresh prepare approval, draft and exact notice approval are required at each rung.
Reasoned refusals produce decision_required and stop automatic escalation. Show the administrator's reply/reason.
Acted, delisted, needs_more_information and uncertain delivery results do not auto-escalate.

Optional POST /api/cases/{id}/reply-analysis accepts {"text":"recipient reply"}.
It returns advisory category/recommendation or model_not_configured. It never updates delivery status
or triggers escalation; machine-readable mock administrator results control that workflow.

The real-time scheduler and POST /api/scheduler/tick use the same function. If LIKENESS_DEMO_CLOCK=1,
POST /api/clock/advance with {"seconds":172801} advances and ticks. Otherwise it returns 422.
The demo clock offset is process-local and resets at restart; stored deadlines remain timestamps.

## Health, storage, errors and limits

Health model.configured means configuration is present. live_call_verified means an invocation completed in
this process. object_storage.remote_verified becomes true only after a successful remote write in this process.
Without OBJ_* configuration, storage is local_disk. Fixture identities are refused when remote storage is configured.

Errors use {"error":{"code":"...","message":"..."}}. Validation may add details; rejected photos add photos.
404 means missing; 409 means an operation is in progress; 422 means invalid input or a refused workflow action.
Handle non-JSON server/network errors too. Long requests can take seconds; disable repeated submissions.

No accounts, identity verification, real submissions or live face-search provider are implemented.
A shared Caddy password protects deployment. APP_PASSWORD_HASH is generated by scripts/hash_password.py using getpass.
Owner-triggered deploy defaults to us-ord and creates a bucket/scoped key, storing OBJ_* only in the remote .env.
Owner-triggered deploy/seed_remote.sh <photo-folder> plants approved photos over SSH and refuses recognizable fixtures.
Neither cloud script was executed during this round. Storage/deploy unit tests do not prove cloud operation.

## Actual captured requests and responses

One real example per method/path/status is included below. Full repeated traces remain in each run's api-examples.json.
Multipart examples identify neutral filenames and byte counts. Binary examples show hashes, not inline photo bytes.
"""
NOTE = """# For the frontend teammate

The backend now supports the full local demo: enrol, find, decide, research a recipient, approve a request,
send it to our test sites, and check what happened.

Give your coding agent FRONTEND_AGENT_BRIEF.md and openapi.json from this folder.
They describe the connections and include responses captured from real local runs.
backend/demo-ui/ has working Decide, Send and Verify screens to copy the interaction patterns from.

Your frontend and port 5173 were left alone. The backend normally uses 8190, with the test console served
from that same address. The separate console development server uses 5183.

Questions begin unanswered. The person provides the facts; fixed rules pick the route.
Each request must be reviewed and approved before sending. Real websites stop at a draft and a named
recipient. Only our local test sites receive automatic requests. A reasoned refusal stops escalation.
Search delisting is shown separately from removal of the original image.

There is no model key yet. Recipient research currently uses a clearly labelled deterministic fallback.
The page description can be absent without blocking the person. The application sends only text and URLs to the model.

The full six-scenario local demo and browser flow passed. This is not a cloud deployment or a real-face
search demo. Cloud scripts are ready for owner review but have not been run. Use approved owner photos
for the real demo; the development research pictures must stay local.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    run1 = Path((ROOT / "data/latest-e2e.txt").read_text().strip())
    run2 = args.run or Path((ROOT / "data/latest-round2.txt").read_text().strip())
    summary = json.loads((run2 / "summary.json").read_text())
    if not summary.get("passed"):
        raise SystemExit("Round 2 acceptance did not pass; refusing to publish a successful handoff")
    examples = []
    seen = set()
    for run in (run1, run2):
        for entry in json.loads((run / "api-examples.json").read_text()):
            normalized = re.sub(r"/(?:[0-9]+|[0-9a-f-]{32,})(?=/|\?|$)", "/{id}", entry["path"].split("?")[0])
            key = (entry["method"], normalized, entry["status"])
            if key not in seen:
                examples.append(entry)
                seen.add(key)
    blocks = [GUIDE, f"\nCaptured runs: {run1.name}, {run2.name}.\n"]
    for entry in examples:
        blocks.append(f"\n### {entry['method']} {entry['path']} (HTTP {entry['status']})\n")
        request = entry["request"]
        command = ["curl", "-sS", "-X", entry["method"]]
        if "json" in request:
            command += ["-H", "Content-Type: application/json", "--data", json.dumps(request["json"])]
        for key, value in request.get("data", {}).items():
            command += ["-F", f"{key}={value}"]
        for file in request.get("files", []):
            command += ["-F", f"{file['field']}=@/your/photos/{file['filename']}"]
        command.append("http://127.0.0.1:8190" + entry["path"])
        blocks.append("\n```sh\n" + shlex.join(command) + "\n```\n")
        blocks.append("\n```json\n" + json.dumps(entry, indent=2) + "\n```\n")
    handoff = ROOT / "handoff"
    (handoff / "FRONTEND_AGENT_BRIEF.md").write_text("".join(blocks))
    (handoff / "NOTE_FOR_PARTNER.md").write_text(NOTE)
    (handoff / "openapi.json").write_bytes((run2 / "openapi.json").read_bytes())
    print(
        json.dumps(
            {
                "examples": len(examples),
                "partner_note_words": len(NOTE.split()),
                "round2_scenarios": summary["scores"]["passed"],
                "runs": [run1.name, run2.name],
            }
        )
    )


if __name__ == "__main__":
    main()
