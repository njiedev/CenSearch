# Frontend agent brief: Likeness Guard round 2

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

Captured runs: e2e-20261010-134427, round2-20261010-135222.

### GET /api/health (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/health
```

```json
{
  "method": "GET",
  "path": "/api/health",
  "request": {},
  "status": 200,
  "response": {
    "status": "ok",
    "database": {
      "status": "ok"
    },
    "face_models": {
      "loaded": true,
      "error": null,
      "calibration_sha256": "c11a2f8fbe7246f5cd73e17e1cf56b0b952e6be09e3499f2fae9c39c6285bf2a"
    },
    "model": {
      "configured": false,
      "provider": "openai_compatible",
      "model": "hackathon-chat",
      "live_call_verified": false
    },
    "object_storage": {
      "configured": false,
      "mode": "local_disk",
      "remote_verified": false
    },
    "external_delivery_enabled": false,
    "public_crawl_enabled": false,
    "busy": false,
    "mock_seeds": [
      "http://127.0.0.1:9011/",
      "http://127.0.0.1:9012/",
      "http://127.0.0.1:9013/",
      "http://127.0.0.1:9014/"
    ]
  }
}
```

### GET /api/people (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/people
```

```json
{
  "method": "GET",
  "path": "/api/people",
  "request": {},
  "status": 200,
  "response": []
}
```

### GET /api/cases (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases
```

```json
{
  "method": "GET",
  "path": "/api/cases",
  "request": {},
  "status": 200,
  "response": []
}
```

### POST /api/people (HTTP 201)

```sh
curl -sS -X POST -F name=demo-person -F 'consent=Local development fixture; no claim of real consent' -F 'ownership=Hypothetical local fixture, not a copyright assertion' -F development_fixture=true -F references=@/your/photos/reference-1.jpg -F references=@/your/photos/reference-2.jpg -F references=@/your/photos/reference-3.jpg -F originals=@/your/photos/originals-1.jpg http://127.0.0.1:8190/api/people
```

```json
{
  "method": "POST",
  "path": "/api/people",
  "request": {
    "data": {
      "name": "demo-person",
      "consent": "Local development fixture; no claim of real consent",
      "ownership": "Hypothetical local fixture, not a copyright assertion",
      "development_fixture": "true"
    },
    "files": [
      {
        "field": "references",
        "filename": "reference-1.jpg",
        "bytes": 12649,
        "content_type": "image/jpeg"
      },
      {
        "field": "references",
        "filename": "reference-2.jpg",
        "bytes": 12326,
        "content_type": "image/jpeg"
      },
      {
        "field": "references",
        "filename": "reference-3.jpg",
        "bytes": 15333,
        "content_type": "image/jpeg"
      },
      {
        "field": "originals",
        "filename": "originals-1.jpg",
        "bytes": 14213,
        "content_type": "image/jpeg"
      }
    ]
  },
  "status": 201,
  "response": {
    "person": {
      "id": "1f0164b6-9415-4ada-8c67-328eb189c000",
      "name": "demo-person",
      "consent": "Local development fixture; no claim of real consent",
      "development_fixture": true,
      "created_at": "2026-10-10T18:44:30.127368+00:00",
      "references": [
        {
          "id": 1,
          "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
          "filename": "reference-1.jpg",
          "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/0.jpg",
          "sha256": "91800e3721b94e82dd47d045ca8ff72f66d3353daa435b3daf282d109d679055",
          "quality": {
            "detector_score": 0.9490012526512146,
            "blur": 196.11512804277604,
            "box": [
              88.69709014892578,
              67.35714721679688,
              97.17683410644531,
              126.6474838256836
            ]
          }
        },
        {
          "id": 2,
          "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
          "filename": "reference-2.jpg",
          "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/1.jpg",
          "sha256": "4d2d1650d37a923d30c158d99905cc0af0a63a76e06bcde3e2e25501683ca8dc",
          "quality": {
            "detector_score": 0.9496399164199829,
            "blur": 269.6945732912404,
            "box": [
              76.60173034667969,
              77.82936096191406,
              87.79450988769531,
              117.97069549560547
            ]
          }
        },
        {
          "id": 3,
          "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
          "filename": "reference-3.jpg",
          "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/2.jpg",
          "sha256": "c048134260619ab89ed5199e6acdc787568c80fa2c79e7436e337053a639c6c5",
          "quality": {
            "detector_score": 0.9314541816711426,
            "blur": 176.53266249710612,
            "box": [
              73.9344482421875,
              63.493247985839844,
              88.68562316894531,
              132.15538024902344
            ]
          }
        }
      ],
      "originals": [
        {
          "id": 1,
          "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
          "filename": "originals-1.jpg",
          "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/originals/0.image",
          "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
          "ownership_statement": "Hypothetical local fixture, not a copyright assertion"
        }
      ],
      "active_reference_count": 3
    },
    "photos": [
      {
        "kind": "reference",
        "index": 0,
        "filename": "reference-1.jpg",
        "accepted": true,
        "reason": null,
        "quality": {
          "detector_score": 0.9490012526512146,
          "blur": 196.11512804277604,
          "box": [
            88.69709014892578,
            67.35714721679688,
            97.17683410644531,
            126.6474838256836
          ]
        }
      },
      {
        "kind": "reference",
        "index": 1,
        "filename": "reference-2.jpg",
        "accepted": true,
        "reason": null,
        "quality": {
          "detector_score": 0.9496399164199829,
          "blur": 269.6945732912404,
          "box": [
            76.60173034667969,
            77.82936096191406,
            87.79450988769531,
            117.97069549560547
          ]
        }
      },
      {
        "kind": "reference",
        "index": 2,
        "filename": "reference-3.jpg",
        "accepted": true,
        "reason": null,
        "quality": {
          "detector_score": 0.9314541816711426,
          "blur": 176.53266249710612,
          "box": [
            73.9344482421875,
            63.493247985839844,
            88.68562316894531,
            132.15538024902344
          ]
        }
      },
      {
        "kind": "original",
        "index": 0,
        "filename": "originals-1.jpg",
        "accepted": true,
        "reason": null
      }
    ]
  }
}
```

### GET /api/people/1f0164b6-9415-4ada-8c67-328eb189c000 (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/people/1f0164b6-9415-4ada-8c67-328eb189c000
```

```json
{
  "method": "GET",
  "path": "/api/people/1f0164b6-9415-4ada-8c67-328eb189c000",
  "request": {},
  "status": 200,
  "response": {
    "id": "1f0164b6-9415-4ada-8c67-328eb189c000",
    "name": "demo-person",
    "consent": "Local development fixture; no claim of real consent",
    "development_fixture": true,
    "created_at": "2026-10-10T18:44:30.127368+00:00",
    "references": [
      {
        "id": 1,
        "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
        "filename": "reference-1.jpg",
        "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/0.jpg",
        "sha256": "91800e3721b94e82dd47d045ca8ff72f66d3353daa435b3daf282d109d679055",
        "quality": {
          "detector_score": 0.9490012526512146,
          "blur": 196.11512804277604,
          "box": [
            88.69709014892578,
            67.35714721679688,
            97.17683410644531,
            126.6474838256836
          ]
        }
      },
      {
        "id": 2,
        "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
        "filename": "reference-2.jpg",
        "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/1.jpg",
        "sha256": "4d2d1650d37a923d30c158d99905cc0af0a63a76e06bcde3e2e25501683ca8dc",
        "quality": {
          "detector_score": 0.9496399164199829,
          "blur": 269.6945732912404,
          "box": [
            76.60173034667969,
            77.82936096191406,
            87.79450988769531,
            117.97069549560547
          ]
        }
      },
      {
        "id": 3,
        "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
        "filename": "reference-3.jpg",
        "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/references/2.jpg",
        "sha256": "c048134260619ab89ed5199e6acdc787568c80fa2c79e7436e337053a639c6c5",
        "quality": {
          "detector_score": 0.9314541816711426,
          "blur": 176.53266249710612,
          "box": [
            73.9344482421875,
            63.493247985839844,
            88.68562316894531,
            132.15538024902344
          ]
        }
      }
    ],
    "originals": [
      {
        "id": 1,
        "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
        "filename": "originals-1.jpg",
        "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/originals/0.image",
        "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
        "ownership_statement": "Hypothetical local fixture, not a copyright assertion"
      }
    ],
    "active_reference_count": 3
  }
}
```

### POST /api/crawls (HTTP 202)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"seeds": ["http://127.0.0.1:9011/", "http://127.0.0.1:9012/", "http://127.0.0.1:9013/", "http://127.0.0.1:9014/"], "rendered": true, "max_pages": 100}' http://127.0.0.1:8190/api/crawls
```

```json
{
  "method": "POST",
  "path": "/api/crawls",
  "request": {
    "json": {
      "seeds": [
        "http://127.0.0.1:9011/",
        "http://127.0.0.1:9012/",
        "http://127.0.0.1:9013/",
        "http://127.0.0.1:9014/"
      ],
      "rendered": true,
      "max_pages": 100
    }
  },
  "status": 202,
  "response": {
    "id": 1,
    "config": {
      "seeds": [
        "http://127.0.0.1:9011/",
        "http://127.0.0.1:9012/",
        "http://127.0.0.1:9013/",
        "http://127.0.0.1:9014/"
      ],
      "rendered": true,
      "delay": 0.05,
      "max_pages": 100
    },
    "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
    "status": "queued",
    "started_at": "2026-10-10T18:44:30.146606+00:00",
    "finished_at": null,
    "metrics": {},
    "errors": []
  }
}
```

### GET /api/crawls/1 (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/crawls/1
```

```json
{
  "method": "GET",
  "path": "/api/crawls/1",
  "request": {},
  "status": 200,
  "response": {
    "id": 1,
    "config": {
      "seeds": [
        "http://127.0.0.1:9011/",
        "http://127.0.0.1:9012/",
        "http://127.0.0.1:9013/",
        "http://127.0.0.1:9014/"
      ],
      "rendered": true,
      "delay": 0.05,
      "max_pages": 100
    },
    "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
    "status": "completed",
    "started_at": "2026-10-10T18:44:30.146606+00:00",
    "finished_at": "2026-10-10T18:44:36.916121+00:00",
    "metrics": {
      "network_requests": 60,
      "pages": 24,
      "discovered": 16,
      "analysed": 16,
      "matches": 12,
      "rendered_pages": 4,
      "robots_denied": 1
    },
    "errors": []
  }
}
```

### GET /api/crawls (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/crawls
```

```json
{
  "method": "GET",
  "path": "/api/crawls",
  "request": {},
  "status": 200,
  "response": [
    {
      "id": 1,
      "config": {
        "seeds": [
          "http://127.0.0.1:9011/",
          "http://127.0.0.1:9012/",
          "http://127.0.0.1:9013/",
          "http://127.0.0.1:9014/"
        ],
        "rendered": true,
        "delay": 0.05,
        "max_pages": 100
      },
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "status": "completed",
      "started_at": "2026-10-10T18:44:30.146606+00:00",
      "finished_at": "2026-10-10T18:44:36.916121+00:00",
      "metrics": {
        "network_requests": 60,
        "pages": 24,
        "discovered": 16,
        "analysed": 16,
        "matches": 12,
        "rendered_pages": 4,
        "robots_denied": 1
      },
      "errors": []
    }
  ]
}
```

### GET /api/scans?run_id=1 (HTTP 200)

```sh
curl -sS -X GET 'http://127.0.0.1:8190/api/scans?run_id=1'
```

```json
{
  "method": "GET",
  "path": "/api/scans?run_id=1",
  "request": {},
  "status": 200,
  "response": [
    {
      "id": 1,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0001.html",
      "image_url": "http://127.0.0.1:9011/media/0001.jpg",
      "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.113033+00:00",
      "status": "matched"
    },
    {
      "id": 2,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0002.html",
      "image_url": "http://127.0.0.1:9011/media/0002.jpg",
      "sha256": "0b7c2010038be3300aaaafdd665cd9963da027e6ef8d8558289e97efa6c6cd8c",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.263638+00:00",
      "status": "matched"
    },
    {
      "id": 3,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0003.html",
      "image_url": "http://127.0.0.1:9011/media/0003.jpg",
      "sha256": "f757086c6a6e8bad36feb58028ee3e290aa4d3a5c1b4202f8393aa496bdbb1ba",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.408377+00:00",
      "status": "matched"
    },
    {
      "id": 4,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0004.html",
      "image_url": "http://127.0.0.1:9011/media/0004.jpg",
      "sha256": "2e7e53617b84b85c9c925b1e00054c9a48b4c913f1664bb8d355d09a144d06c5",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.553350+00:00",
      "status": "matched"
    },
    {
      "id": 5,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0005.html",
      "image_url": "http://127.0.0.1:9011/media/0005.jpg",
      "sha256": "af1ceb6fe12e30e4d7d7b15ef69bcd966412ef1f4925915c0382f6c35890f3ea",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.687322+00:00",
      "status": "matched"
    },
    {
      "id": 6,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0006.html",
      "image_url": "http://127.0.0.1:9011/media/0006.jpg",
      "sha256": "a0b986022cf5cde53fb21a4b0fe5c132d1e75418c5817382a792b61f93b78b36",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.832046+00:00",
      "status": "matched"
    },
    {
      "id": 7,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0007.html",
      "image_url": "http://127.0.0.1:9011/media/0007.jpg",
      "sha256": "74dee5b4d9fa8a0dea384ba5c692ec7eb9523809c96bc28a72eb33fec2361968",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:31.981510+00:00",
      "status": "matched"
    },
    {
      "id": 8,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9011/post/0014.html",
      "image_url": "http://127.0.0.1:9011/media/0014.jpg",
      "sha256": "a51bc923f44b12b40ca1aeb716fc9b206343d5957f903b997b5d3f55b3528ef0",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:32.190990+00:00",
      "status": "no_match"
    },
    {
      "id": 9,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9012/post/0008.html",
      "image_url": "http://127.0.0.1:9012/media/0008.jpg",
      "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:33.327285+00:00",
      "status": "matched"
    },
    {
      "id": 10,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9012/post/0009.html",
      "image_url": "http://127.0.0.1:9012/media/0009.jpg",
      "sha256": "4b5b66eda030f678c02d369a332862eef2183a277ce0047952355204ebdc09f2",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:34.290197+00:00",
      "status": "matched"
    },
    {
      "id": 11,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9012/post/0010.html",
      "image_url": "http://127.0.0.1:9012/media/0010.jpg",
      "sha256": "b075767c06d6069df70bcf4400c1be6824c2b0a97db3f94fc267f899fd1206be",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:35.289284+00:00",
      "status": "matched"
    },
    {
      "id": 12,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9012/post/0015.html",
      "image_url": "http://127.0.0.1:9012/media/0015.jpg",
      "sha256": "38512b30ab2b94fbc7268cba44e92463fbac1704bae8d991daaf243af72d7d7d",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:36.270236+00:00",
      "status": "no_match"
    },
    {
      "id": 13,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9013/post/0011.html",
      "image_url": "http://127.0.0.1:9013/media/0011.jpg",
      "sha256": "72789d28b535e9a5b6721a16e1288e66e734f7ac815a63722c02a459206c68ff",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:36.352125+00:00",
      "status": "matched"
    },
    {
      "id": 14,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9013/post/0016.html",
      "image_url": "http://127.0.0.1:9013/media/0016.jpg",
      "sha256": "8a471fcfc504dfe8d8282944aa4000716be6edef51ccb69981f6e22f1cdbede9",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:36.476034+00:00",
      "status": "no_match"
    },
    {
      "id": 15,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9014/post/0012.html",
      "image_url": "http://127.0.0.1:9014/media/0012.jpg",
      "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:36.604290+00:00",
      "status": "matched"
    },
    {
      "id": 16,
      "run_id": 1,
      "page_url": "http://127.0.0.1:9014/post/0017.html",
      "image_url": "http://127.0.0.1:9014/media/0017.jpg",
      "sha256": "8dbe40b5f7f24a1164cbf1cdbe785b682441d6976d305757fc50252f8e78b1ce",
      "identity_version": "e0dc98b46004a07948681e0869e929a946036fdf1d62921b55bcd1d035d07fb0",
      "scanned_at": "2026-10-10T18:44:36.730429+00:00",
      "status": "no_match"
    }
  ]
}
```

### GET /api/cases/1/image (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/1/image
```

```json
{
  "method": "GET",
  "path": "/api/cases/1/image",
  "request": {},
  "status": 200,
  "response": {
    "content_type": "image/jpeg",
    "byte_length": 14213,
    "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b"
  }
}
```

### GET /api/cases/1 (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/1
```

```json
{
  "method": "GET",
  "path": "/api/cases/1",
  "request": {},
  "status": 200,
  "response": {
    "id": 1,
    "person_id": "1f0164b6-9415-4ada-8c67-328eb189c000",
    "scan_id": 1,
    "original_id": 1,
    "page_url": "http://127.0.0.1:9011/post/0001.html",
    "image_url": "http://127.0.0.1:9011/media/0001.jpg",
    "match_type": "both",
    "band": "match",
    "score": 0.746055543422699,
    "face_band": "match",
    "face_score": 0.746055543422699,
    "copy_relation": "exact",
    "photo_relation": "same_photo",
    "evidence": {
      "calibration_sha256": "c11a2f8fbe7246f5cd73e17e1cf56b0b952e6be09e3499f2fae9c39c6285bf2a",
      "fusion": "max",
      "phash": "2db4626dc39118fc",
      "face": {
        "box": [
          66.58499908447266,
          65.15089416503906,
          98.93453979492188,
          124.93463897705078
        ],
        "box_coordinates": "EXIF-oriented native pixels",
        "detector_score": 0.9349603056907654,
        "blur": 613.8152848337925,
        "reference_count": 3,
        "active_reference_count": 3,
        "bands": {
          "possible": {
            "threshold": 0.42569765448570257,
            "target_far": 0.01,
            "measured_far": 0.01,
            "false_accepts": 20,
            "negative_trials": 2000,
            "resolution": 0.0005,
            "zero_error_95_upper": null
          },
          "match": {
            "threshold": 0.4757652580738068,
            "target_far": 0.001,
            "measured_far": 0.001,
            "false_accepts": 2,
            "negative_trials": 2000,
            "resolution": 0.0005,
            "zero_error_95_upper": null
          }
        }
      },
      "copy": {
        "sha256_equal": true
      },
      "context": {
        "title": "pixboard",
        "author": "",
        "extraction": "src",
        "alt": "Shared photograph",
        "caption": "Posted by demo-person",
        "nearby_text": "Posted by demo-person"
      },
      "score_basis": "face_cosine_similarity",
      "photo_relation_basis": "protected_work_verified",
      "image": {
        "path": "people/1f0164b6-9415-4ada-8c67-328eb189c000/evidence/1-a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b.image",
        "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
        "byte_length": 14213,
        "storage": "local",
        "object_key": null,
        "response_headers": {
          "server": "SimpleHTTP/0.6 Python/3.12.12",
          "date": "Sat, 10 Oct 2026 18:44:31 GMT",
          "content-type": "image/jpeg",
          "last-modified": "Sat, 10 Oct 2026 18:44:27 GMT",
          "content-length": "14213"
        },
        "fetched_at": "2026-10-10T18:44:31.256865+00:00",
        "final_url": "http://127.0.0.1:9011/media/0001.jpg",
        "source": "http"
      }
    },
    "state": "needs_review",
    "created_at": "2026-10-10T18:44:31.257681+00:00",
    "answers": null,
    "route": null,
    "drafted_request": null,
    "recipients": [],
    "deliveries": [],
    "verification_checks": [],
    "matched_image_url": "/api/cases/1/image"
  }
}
```

### GET /api/cases/999999 (HTTP 404)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/999999
```

```json
{
  "method": "GET",
  "path": "/api/cases/999999",
  "request": {},
  "status": 404,
  "response": {
    "error": {
      "code": "not_found",
      "message": "Case not found"
    }
  }
}
```

### POST /api/crawls (HTTP 422)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"seeds": []}' http://127.0.0.1:8190/api/crawls
```

```json
{
  "method": "POST",
  "path": "/api/crawls",
  "request": {
    "json": {
      "seeds": []
    }
  },
  "status": 422,
  "response": {
    "error": {
      "code": "validation_error",
      "message": "Invalid request",
      "details": [
        {
          "location": [
            "body",
            "seeds"
          ],
          "message": "List should have at least 1 item after validation, not 0",
          "type": "too_short"
        }
      ]
    }
  }
}
```

### POST /api/people (HTTP 422)

```sh
curl -sS -X POST -F 'name=Bad fixture' -F 'consent=Local testing' -F references=@/your/photos/bad.jpg http://127.0.0.1:8190/api/people
```

```json
{
  "method": "POST",
  "path": "/api/people",
  "request": {
    "data": {
      "name": "Bad fixture",
      "consent": "Local testing"
    },
    "files": [
      {
        "field": "references",
        "filename": "bad.jpg",
        "bytes": 12,
        "content_type": "image/jpeg"
      }
    ]
  },
  "status": 422,
  "response": {
    "error": {
      "code": "photo_rejected",
      "message": "No person saved. Remove or replace rejected photos and retry.",
      "photos": [
        {
          "kind": "reference",
          "index": 0,
          "filename": "bad.jpg",
          "accepted": false,
          "reason": "Not a decodable image, or image is too large"
        }
      ]
    }
  }
}
```

### POST /api/agent/probe (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"hostname": "localhost"}' http://127.0.0.1:8190/api/agent/probe
```

```json
{
  "method": "POST",
  "path": "/api/agent/probe",
  "request": {
    "json": {
      "hostname": "localhost"
    }
  },
  "status": 200,
  "response": {
    "status": "model_not_configured",
    "answer": null,
    "tool_calls": [],
    "message": "Model not configured. Set OPENAI_API_KEY in backend/.env."
  }
}
```

### DELETE /api/people/1f0164b6-9415-4ada-8c67-328eb189c000 (HTTP 200)

```sh
curl -sS -X DELETE http://127.0.0.1:8190/api/people/1f0164b6-9415-4ada-8c67-328eb189c000
```

```json
{
  "method": "DELETE",
  "path": "/api/people/1f0164b6-9415-4ada-8c67-328eb189c000",
  "request": {},
  "status": 200,
  "response": {
    "deleted": "1f0164b6-9415-4ada-8c67-328eb189c000"
  }
}
```

### POST /api/cases/1/send (HTTP 422)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/send
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/send",
  "request": {},
  "status": 422,
  "response": {
    "error": {
      "code": "validation_error",
      "message": "Approve the current exact notice before sending"
    }
  }
}
```

### POST /api/cases/1/draft (HTTP 422)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"recipient_id": "missing"}' http://127.0.0.1:8190/api/cases/1/draft
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/draft",
  "request": {
    "json": {
      "recipient_id": "missing"
    }
  },
  "status": 422,
  "response": {
    "error": {
      "code": "validation_error",
      "message": "Explicit approval is required before drafting, including each escalation rung"
    }
  }
}
```

### POST /api/cases/1/verify (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/verify
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/verify",
  "request": {},
  "status": 200,
  "response": {
    "outcome": "blocked",
    "source_removed": false,
    "page_status": 200,
    "image_status": 403,
    "origin_status": null,
    "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
    "requests": [
      {
        "url": "http://127.0.0.1:9111/robots.txt",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/plain",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/html",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/media/0001.jpg",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/media/0001.jpg",
        "method": "GET",
        "status": 403,
        "headers": {
          "content-type": "text/html;charset=utf-8",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      }
    ],
    "checked_at": "2026-10-10T18:52:27.957587+00:00"
  }
}
```

### GET /api/cases/1/workflow (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/1/workflow
```

```json
{
  "method": "GET",
  "path": "/api/cases/1/workflow",
  "request": {},
  "status": 200,
  "response": {
    "case_id": 1,
    "state": "replaced",
    "revision": 0,
    "questions": {
      "identity_confirmed": "Is this you?",
      "owns_photo": "Do you own this exact photo?",
      "authorized_use": "Did you agree to this use?",
      "impersonates_me": "Is the page pretending to be you?",
      "intimate": "Is it an intimate image?",
      "privacy_request": "Do you want it removed for privacy?"
    },
    "additional_questions": {
      "legitimate_use": "Is this a legitimate use you want to leave alone?",
      "identifiable": "Are you identifiable in the intimate image?",
      "good_faith": "Do you believe in good faith that this use lacks permission or legal authorization?",
      "accurate": "Is the information you supplied accurate?",
      "authority_under_perjury": "Under penalty of perjury, are you authorized to act for the copyright owner?"
    },
    "answers": {
      "identity_confirmed": null,
      "owns_photo": null,
      "authorized_use": null,
      "impersonates_me": null,
      "intimate": null,
      "privacy_request": null,
      "legitimate_use": null,
      "identifiable": null,
      "good_faith": null,
      "accurate": null,
      "authority_under_perjury": null
    },
    "contact": {},
    "decision": {},
    "description": {},
    "lookup": {},
    "bundle": {},
    "next_rung": "site",
    "attestations": [],
    "notices": [],
    "deliveries": [],
    "draft_approvals": [],
    "timeline": [
      {
        "id": 1,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "blocked",
          "source_removed": false,
          "page_status": 200,
          "image_status": 403,
          "origin_status": null,
          "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 403,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:27.957587+00:00"
        },
        "at": "2026-10-10T18:52:27.958410+00:00"
      },
      {
        "id": 2,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "page_status": 200,
          "image_status": 503,
          "origin_status": null,
          "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 503,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:28.072874+00:00"
        },
        "at": "2026-10-10T18:52:28.073549+00:00"
      },
      {
        "id": 3,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "error": "ReadTimeout",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "error": "ReadTimeout"
            }
          ],
          "checked_at": "2026-10-10T18:52:31.186749+00:00"
        },
        "at": "2026-10-10T18:52:31.187458+00:00"
      },
      {
        "id": 4,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "replaced",
          "source_removed": false,
          "page_status": 200,
          "image_status": 200,
          "origin_status": null,
          "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "image/jpeg",
                "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:31.346391+00:00"
        },
        "at": "2026-10-10T18:52:31.346960+00:00"
      }
    ],
    "checks": [
      {
        "outcome": "blocked",
        "source_removed": false,
        "page_status": 200,
        "image_status": 403,
        "origin_status": null,
        "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 403,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:27.957587+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "page_status": 200,
        "image_status": 503,
        "origin_status": null,
        "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 503,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:28.072874+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "error": "ReadTimeout",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "error": "ReadTimeout"
          }
        ],
        "checked_at": "2026-10-10T18:52:31.186749+00:00"
      },
      {
        "outcome": "replaced",
        "source_removed": false,
        "page_status": 200,
        "image_status": 200,
        "origin_status": null,
        "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "image/jpeg",
              "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:31.346391+00:00"
      }
    ],
    "clock": "2026-10-10T18:52:32.327695+00:00",
    "demo_clock": true
  }
}
```

### POST /api/cases/1/description (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/description
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/description",
  "request": {},
  "status": 200,
  "response": {
    "status": "model_not_configured",
    "description": null,
    "advisory": true
  }
}
```

### POST /api/cases/1/answers (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"answered_by": "Demo operator", "answers": {"identity_confirmed": true, "owns_photo": true, "authorized_use": false, "impersonates_me": null, "intimate": null, "privacy_request": null, "legitimate_use": null, "identifiable": null, "good_faith": true, "accurate": true, "authority_under_perjury": true, "work_description": "Hypothetical local fixture original; no actual ownership claim"}, "contact": {"name": "Demo operator", "email": "operator@example.test", "signature": "Demo operator", "address": "Local fixture address", "phone": "555-0100"}}' http://127.0.0.1:8190/api/cases/1/answers
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/answers",
  "request": {
    "json": {
      "answered_by": "Demo operator",
      "answers": {
        "identity_confirmed": true,
        "owns_photo": true,
        "authorized_use": false,
        "impersonates_me": null,
        "intimate": null,
        "privacy_request": null,
        "legitimate_use": null,
        "identifiable": null,
        "good_faith": true,
        "accurate": true,
        "authority_under_perjury": true,
        "work_description": "Hypothetical local fixture original; no actual ownership claim"
      },
      "contact": {
        "name": "Demo operator",
        "email": "operator@example.test",
        "signature": "Demo operator",
        "address": "Local fixture address",
        "phone": "555-0100"
      }
    }
  },
  "status": 200,
  "response": {
    "case_id": 1,
    "state": "decided",
    "revision": 1,
    "questions": {
      "identity_confirmed": "Is this you?",
      "owns_photo": "Do you own this exact photo?",
      "authorized_use": "Did you agree to this use?",
      "impersonates_me": "Is the page pretending to be you?",
      "intimate": "Is it an intimate image?",
      "privacy_request": "Do you want it removed for privacy?"
    },
    "additional_questions": {
      "legitimate_use": "Is this a legitimate use you want to leave alone?",
      "identifiable": "Are you identifiable in the intimate image?",
      "good_faith": "Do you believe in good faith that this use lacks permission or legal authorization?",
      "accurate": "Is the information you supplied accurate?",
      "authority_under_perjury": "Under penalty of perjury, are you authorized to act for the copyright owner?"
    },
    "answers": {
      "identity_confirmed": true,
      "owns_photo": true,
      "authorized_use": false,
      "impersonates_me": null,
      "intimate": null,
      "privacy_request": null,
      "legitimate_use": null,
      "identifiable": null,
      "good_faith": true,
      "accurate": true,
      "authority_under_perjury": true,
      "work_description": "Hypothetical local fixture original; no actual ownership claim",
      "explanation": null
    },
    "contact": {
      "name": "Demo operator",
      "email": "operator@example.test",
      "address": "Local fixture address",
      "phone": "555-0100",
      "signature": "Demo operator"
    },
    "decision": {
      "route": "copyright_notice",
      "rule_id": "owned_verified_same_photo",
      "version": "rules-v2",
      "inputs": {
        "answers": {
          "identity_confirmed": true,
          "owns_photo": true,
          "authorized_use": false,
          "impersonates_me": null,
          "intimate": null,
          "privacy_request": null,
          "legitimate_use": null,
          "identifiable": null,
          "good_faith": true,
          "accurate": true,
          "authority_under_perjury": true,
          "work_description": "Hypothetical local fixture original; no actual ownership claim",
          "explanation": null
        },
        "evidence": {
          "copy_relation": "exact",
          "photo_relation": "same_photo",
          "original_id": 1
        }
      }
    },
    "description": {
      "status": "model_not_configured",
      "description": null,
      "advisory": true
    },
    "lookup": {},
    "bundle": {},
    "next_rung": "site",
    "attestations": [
      {
        "id": 1,
        "case_id": 1,
        "question": "identity_confirmed",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424696+00:00"
      },
      {
        "id": 2,
        "case_id": 1,
        "question": "owns_photo",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424743+00:00"
      },
      {
        "id": 3,
        "case_id": 1,
        "question": "authorized_use",
        "value": {
          "answer": false
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424756+00:00"
      },
      {
        "id": 4,
        "case_id": 1,
        "question": "good_faith",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424765+00:00"
      },
      {
        "id": 5,
        "case_id": 1,
        "question": "accurate",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424772+00:00"
      },
      {
        "id": 6,
        "case_id": 1,
        "question": "authority_under_perjury",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424779+00:00"
      },
      {
        "id": 7,
        "case_id": 1,
        "question": "work_description",
        "value": {
          "answer": "Hypothetical local fixture original; no actual ownership claim"
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424786+00:00"
      }
    ],
    "notices": [],
    "deliveries": [],
    "draft_approvals": [],
    "timeline": [
      {
        "id": 1,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "blocked",
          "source_removed": false,
          "page_status": 200,
          "image_status": 403,
          "origin_status": null,
          "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 403,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:27.957587+00:00"
        },
        "at": "2026-10-10T18:52:27.958410+00:00"
      },
      {
        "id": 2,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "page_status": 200,
          "image_status": 503,
          "origin_status": null,
          "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 503,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:28.072874+00:00"
        },
        "at": "2026-10-10T18:52:28.073549+00:00"
      },
      {
        "id": 3,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "error": "ReadTimeout",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "error": "ReadTimeout"
            }
          ],
          "checked_at": "2026-10-10T18:52:31.186749+00:00"
        },
        "at": "2026-10-10T18:52:31.187458+00:00"
      },
      {
        "id": 4,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "replaced",
          "source_removed": false,
          "page_status": 200,
          "image_status": 200,
          "origin_status": null,
          "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "image/jpeg",
                "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:31.346391+00:00"
        },
        "at": "2026-10-10T18:52:31.346960+00:00"
      },
      {
        "id": 5,
        "case_id": 1,
        "kind": "page_described",
        "details": {
          "status": "model_not_configured",
          "description": null,
          "advisory": true
        },
        "at": "2026-10-10T18:52:32.344307+00:00"
      },
      {
        "id": 6,
        "case_id": 1,
        "kind": "contact_saved",
        "details": {
          "contact": {
            "name": "Demo operator",
            "email": "operator@example.test",
            "address": "Local fixture address",
            "phone": "555-0100",
            "signature": "Demo operator"
          },
          "answered_by": "Demo operator",
          "revision": 1
        },
        "at": "2026-10-10T18:52:32.424803+00:00"
      },
      {
        "id": 7,
        "case_id": 1,
        "kind": "route_decided",
        "details": {
          "route": "copyright_notice",
          "rule_id": "owned_verified_same_photo",
          "version": "rules-v2",
          "inputs": {
            "answers": {
              "identity_confirmed": true,
              "owns_photo": true,
              "authorized_use": false,
              "impersonates_me": null,
              "intimate": null,
              "privacy_request": null,
              "legitimate_use": null,
              "identifiable": null,
              "good_faith": true,
              "accurate": true,
              "authority_under_perjury": true,
              "work_description": "Hypothetical local fixture original; no actual ownership claim",
              "explanation": null
            },
            "evidence": {
              "copy_relation": "exact",
              "photo_relation": "same_photo",
              "original_id": 1
            }
          },
          "revision": 1
        },
        "at": "2026-10-10T18:52:32.424824+00:00"
      }
    ],
    "checks": [
      {
        "outcome": "blocked",
        "source_removed": false,
        "page_status": 200,
        "image_status": 403,
        "origin_status": null,
        "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 403,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:27.957587+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "page_status": 200,
        "image_status": 503,
        "origin_status": null,
        "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 503,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:28.072874+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "error": "ReadTimeout",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "error": "ReadTimeout"
          }
        ],
        "checked_at": "2026-10-10T18:52:31.186749+00:00"
      },
      {
        "outcome": "replaced",
        "source_removed": false,
        "page_status": 200,
        "image_status": 200,
        "origin_status": null,
        "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "image/jpeg",
              "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:31.346391+00:00"
      }
    ],
    "clock": "2026-10-10T18:52:32.428307+00:00",
    "demo_clock": true
  }
}
```

### POST /api/cases/1/evidence (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/evidence
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/evidence",
  "request": {},
  "status": 200,
  "response": {
    "page_url": "http://127.0.0.1:9111/post/0001.html",
    "final_url": "http://127.0.0.1:9111/post/0001.html",
    "captured_at": "2026-10-10T18:52:32.472047+00:00",
    "image": {
      "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/1-a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b.image",
      "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
      "byte_length": 14213,
      "storage": "local",
      "object_key": null,
      "response_headers": {
        "server": "SimpleHTTP/0.6 Python/3.12.12",
        "date": "Sat, 10 Oct 2026 18:52:26 GMT",
        "content-type": "image/jpeg",
        "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
        "content-length": "14213"
      },
      "fetched_at": "2026-10-10T18:52:26.108781+00:00",
      "final_url": "http://127.0.0.1:9111/media/0001.jpg",
      "source": "http"
    },
    "image_sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
    "screenshot": {
      "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.png",
      "sha256": "93d0b3ff92465ba2045fb26f05e3ca2db3bf3614b0dc38eb81d2d6aa53008f8d",
      "byte_length": 91423,
      "storage": "local",
      "object_key": null
    },
    "page_response_headers": {
      "content-length": "274",
      "content-type": "text/html",
      "date": "Sat, 10 Oct 2026 18:52:32 GMT",
      "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
      "server": "SimpleHTTP/0.6 Python/3.12.12"
    },
    "requests": [
      {
        "url": "http://127.0.0.1:9111/robots.txt",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/plain",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/html",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/media/0001.jpg",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/media/0001.jpg",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "image/jpeg",
          "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      }
    ],
    "screenshot_url": "/api/cases/1/screenshot",
    "bundle_file": {
      "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.json",
      "sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
      "byte_length": 2582,
      "storage": "local",
      "object_key": null
    }
  }
}
```

### POST /api/cases/1/recipients (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/recipients
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/recipients",
  "request": {},
  "status": 200,
  "response": {
    "source": "deterministic_baseline",
    "status": "completed",
    "model_status": "model_not_configured",
    "recipients": [
      {
        "rung": "site",
        "channel": "smtp",
        "address": "agent@pixboard.test",
        "endpoint": "smtp://127.0.0.1:9118",
        "evidence": {
          "source": "http://127.0.0.1:9111/policy",
          "method": "published_email",
          "link_text": "Copyright and privacy contact"
        },
        "id": "contact-1",
        "rank": 1
      },
      {
        "rung": "search",
        "channel": "http_form",
        "address": "http://127.0.0.1:9116/report",
        "endpoint": "http://127.0.0.1:9116/report",
        "evidence": {
          "source": "platform-registry-2026-10-10",
          "method": "search_registry",
          "scope": "Delisting only; source remains"
        },
        "id": "contact-2",
        "rank": 2
      }
    ],
    "tool_calls": [
      {
        "tool": "fetch_page",
        "input": {
          "url": "http://127.0.0.1:9111/post/0001.html"
        },
        "result": {
          "status": 200,
          "final_url": "http://127.0.0.1:9111/post/0001.html",
          "title": "pixboard",
          "text": "pixboard Posted by demo-person Content policy and reports",
          "links": [
            {
              "url": "http://127.0.0.1:9111/policy",
              "text": "Content policy and reports"
            }
          ],
          "forms": [],
          "headers": {
            "content-type": "text/html",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          },
          "contacts": []
        }
      },
      {
        "tool": "fetch_page",
        "input": {
          "url": "http://127.0.0.1:9111/post/0001.html"
        },
        "result": {
          "status": 200,
          "final_url": "http://127.0.0.1:9111/post/0001.html",
          "title": "pixboard",
          "text": "pixboard Posted by demo-person Content policy and reports",
          "links": [
            {
              "url": "http://127.0.0.1:9111/policy",
              "text": "Content policy and reports"
            }
          ],
          "forms": [],
          "headers": {
            "content-type": "text/html",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          },
          "contacts": []
        }
      },
      {
        "tool": "find_policy_pages",
        "input": {
          "url": "http://127.0.0.1:9111/post/0001.html"
        },
        "result": {
          "status": 200,
          "source": "http://127.0.0.1:9111/post/0001.html",
          "links": [
            {
              "url": "http://127.0.0.1:9111/policy",
              "text": "Content policy and reports"
            }
          ]
        }
      },
      {
        "tool": "fetch_page",
        "input": {
          "url": "http://127.0.0.1:9111/policy"
        },
        "result": {
          "status": 200,
          "final_url": "http://127.0.0.1:9111/policy",
          "title": "",
          "text": "DMCA and privacy agent Copyright and privacy contact",
          "links": [
            {
              "url": "mailto:agent@pixboard.test",
              "text": "Copyright and privacy contact"
            }
          ],
          "forms": [],
          "headers": {
            "content-type": "text/html",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          },
          "contacts": [
            {
              "rung": "site",
              "channel": "smtp",
              "address": "agent@pixboard.test",
              "endpoint": "smtp://127.0.0.1:9118",
              "evidence": {
                "source": "http://127.0.0.1:9111/policy",
                "method": "published_email",
                "link_text": "Copyright and privacy contact"
              },
              "id": "contact-1"
            }
          ]
        }
      },
      {
        "tool": "dns_lookup",
        "input": {
          "hostname": "127.0.0.1"
        },
        "result": {
          "hostname": "127.0.0.1",
          "status": "resolved",
          "addresses": [
            "127.0.0.1"
          ],
          "cnames": [],
          "caution": "DNS/CDN addresses do not prove the origin hosting provider."
        }
      },
      {
        "tool": "rdap_lookup",
        "input": {
          "ip_or_domain": "127.0.0.1"
        },
        "result": {
          "status": "completed",
          "bootstrap": "http://127.0.0.1:9117/bootstrap",
          "registry_url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
          "name": "Mock loopback allocation",
          "contacts": []
        }
      },
      {
        "tool": "platform_registry",
        "input": {
          "hostname": "127.0.0.1"
        },
        "result": {
          "version": "2026-10-10",
          "contacts": [
            {
              "rung": "search",
              "channel": "http_form",
              "address": "http://127.0.0.1:9116/report",
              "endpoint": "http://127.0.0.1:9116/report",
              "evidence": {
                "source": "platform-registry-2026-10-10",
                "method": "search_registry",
                "scope": "Delisting only; source remains"
              },
              "id": "contact-2"
            }
          ]
        }
      }
    ],
    "requests": [
      {
        "url": "http://127.0.0.1:9111/robots.txt",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/plain",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/post/0001.html",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/html",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9111/policy",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9111/policy",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/html",
          "server": "SimpleHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9117/robots.txt",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "text/plain",
          "server": "BaseHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9117/bootstrap",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9117/bootstrap",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "application/json",
          "server": "BaseHTTP/0.6 Python/3.12.12"
        }
      },
      {
        "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
        "robots_allowed": true
      },
      {
        "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
        "method": "GET",
        "status": 200,
        "headers": {
          "content-type": "application/json",
          "server": "BaseHTTP/0.6 Python/3.12.12"
        }
      }
    ],
    "page_status": 200,
    "limitations": [
      "Published contacts require human review.",
      "CDN/RDAP contacts may identify a serving network rather than the origin."
    ]
  }
}
```

### POST /api/cases/1/approve-draft (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"approved_by": "Demo operator", "revision": 1, "rung": "site"}' http://127.0.0.1:8190/api/cases/1/approve-draft
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/approve-draft",
  "request": {
    "json": {
      "approved_by": "Demo operator",
      "revision": 1,
      "rung": "site"
    }
  },
  "status": 200,
  "response": {
    "case_id": 1,
    "state": "decided",
    "revision": 1,
    "questions": {
      "identity_confirmed": "Is this you?",
      "owns_photo": "Do you own this exact photo?",
      "authorized_use": "Did you agree to this use?",
      "impersonates_me": "Is the page pretending to be you?",
      "intimate": "Is it an intimate image?",
      "privacy_request": "Do you want it removed for privacy?"
    },
    "additional_questions": {
      "legitimate_use": "Is this a legitimate use you want to leave alone?",
      "identifiable": "Are you identifiable in the intimate image?",
      "good_faith": "Do you believe in good faith that this use lacks permission or legal authorization?",
      "accurate": "Is the information you supplied accurate?",
      "authority_under_perjury": "Under penalty of perjury, are you authorized to act for the copyright owner?"
    },
    "answers": {
      "identity_confirmed": true,
      "owns_photo": true,
      "authorized_use": false,
      "impersonates_me": null,
      "intimate": null,
      "privacy_request": null,
      "legitimate_use": null,
      "identifiable": null,
      "good_faith": true,
      "accurate": true,
      "authority_under_perjury": true,
      "work_description": "Hypothetical local fixture original; no actual ownership claim",
      "explanation": null
    },
    "contact": {
      "name": "Demo operator",
      "email": "operator@example.test",
      "address": "Local fixture address",
      "phone": "555-0100",
      "signature": "Demo operator"
    },
    "decision": {
      "route": "copyright_notice",
      "rule_id": "owned_verified_same_photo",
      "version": "rules-v2",
      "inputs": {
        "answers": {
          "identity_confirmed": true,
          "owns_photo": true,
          "authorized_use": false,
          "impersonates_me": null,
          "intimate": null,
          "privacy_request": null,
          "legitimate_use": null,
          "identifiable": null,
          "good_faith": true,
          "accurate": true,
          "authority_under_perjury": true,
          "work_description": "Hypothetical local fixture original; no actual ownership claim",
          "explanation": null
        },
        "evidence": {
          "copy_relation": "exact",
          "photo_relation": "same_photo",
          "original_id": 1
        }
      }
    },
    "description": {
      "status": "model_not_configured",
      "description": null,
      "advisory": true
    },
    "lookup": {
      "source": "deterministic_baseline",
      "status": "completed",
      "model_status": "model_not_configured",
      "recipients": [
        {
          "rung": "site",
          "channel": "smtp",
          "address": "agent@pixboard.test",
          "endpoint": "smtp://127.0.0.1:9118",
          "evidence": {
            "source": "http://127.0.0.1:9111/policy",
            "method": "published_email",
            "link_text": "Copyright and privacy contact"
          },
          "id": "contact-1",
          "rank": 1
        },
        {
          "rung": "search",
          "channel": "http_form",
          "address": "http://127.0.0.1:9116/report",
          "endpoint": "http://127.0.0.1:9116/report",
          "evidence": {
            "source": "platform-registry-2026-10-10",
            "method": "search_registry",
            "scope": "Delisting only; source remains"
          },
          "id": "contact-2",
          "rank": 2
        }
      ],
      "tool_calls": [
        {
          "tool": "fetch_page",
          "input": {
            "url": "http://127.0.0.1:9111/post/0001.html"
          },
          "result": {
            "status": 200,
            "final_url": "http://127.0.0.1:9111/post/0001.html",
            "title": "pixboard",
            "text": "pixboard Posted by demo-person Content policy and reports",
            "links": [
              {
                "url": "http://127.0.0.1:9111/policy",
                "text": "Content policy and reports"
              }
            ],
            "forms": [],
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            },
            "contacts": []
          }
        },
        {
          "tool": "fetch_page",
          "input": {
            "url": "http://127.0.0.1:9111/post/0001.html"
          },
          "result": {
            "status": 200,
            "final_url": "http://127.0.0.1:9111/post/0001.html",
            "title": "pixboard",
            "text": "pixboard Posted by demo-person Content policy and reports",
            "links": [
              {
                "url": "http://127.0.0.1:9111/policy",
                "text": "Content policy and reports"
              }
            ],
            "forms": [],
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            },
            "contacts": []
          }
        },
        {
          "tool": "find_policy_pages",
          "input": {
            "url": "http://127.0.0.1:9111/post/0001.html"
          },
          "result": {
            "status": 200,
            "source": "http://127.0.0.1:9111/post/0001.html",
            "links": [
              {
                "url": "http://127.0.0.1:9111/policy",
                "text": "Content policy and reports"
              }
            ]
          }
        },
        {
          "tool": "fetch_page",
          "input": {
            "url": "http://127.0.0.1:9111/policy"
          },
          "result": {
            "status": 200,
            "final_url": "http://127.0.0.1:9111/policy",
            "title": "",
            "text": "DMCA and privacy agent Copyright and privacy contact",
            "links": [
              {
                "url": "mailto:agent@pixboard.test",
                "text": "Copyright and privacy contact"
              }
            ],
            "forms": [],
            "headers": {
              "content-type": "text/html",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            },
            "contacts": [
              {
                "rung": "site",
                "channel": "smtp",
                "address": "agent@pixboard.test",
                "endpoint": "smtp://127.0.0.1:9118",
                "evidence": {
                  "source": "http://127.0.0.1:9111/policy",
                  "method": "published_email",
                  "link_text": "Copyright and privacy contact"
                },
                "id": "contact-1"
              }
            ]
          }
        },
        {
          "tool": "dns_lookup",
          "input": {
            "hostname": "127.0.0.1"
          },
          "result": {
            "hostname": "127.0.0.1",
            "status": "resolved",
            "addresses": [
              "127.0.0.1"
            ],
            "cnames": [],
            "caution": "DNS/CDN addresses do not prove the origin hosting provider."
          }
        },
        {
          "tool": "rdap_lookup",
          "input": {
            "ip_or_domain": "127.0.0.1"
          },
          "result": {
            "status": "completed",
            "bootstrap": "http://127.0.0.1:9117/bootstrap",
            "registry_url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
            "name": "Mock loopback allocation",
            "contacts": []
          }
        },
        {
          "tool": "platform_registry",
          "input": {
            "hostname": "127.0.0.1"
          },
          "result": {
            "version": "2026-10-10",
            "contacts": [
              {
                "rung": "search",
                "channel": "http_form",
                "address": "http://127.0.0.1:9116/report",
                "endpoint": "http://127.0.0.1:9116/report",
                "evidence": {
                  "source": "platform-registry-2026-10-10",
                  "method": "search_registry",
                  "scope": "Delisting only; source remains"
                },
                "id": "contact-2"
              }
            ]
          }
        }
      ],
      "requests": [
        {
          "url": "http://127.0.0.1:9111/robots.txt",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/plain",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9111/post/0001.html",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9111/post/0001.html",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/html",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9111/policy",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9111/policy",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/html",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9117/robots.txt",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/plain",
            "server": "BaseHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9117/bootstrap",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9117/bootstrap",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "application/json",
            "server": "BaseHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "application/json",
            "server": "BaseHTTP/0.6 Python/3.12.12"
          }
        }
      ],
      "page_status": 200,
      "limitations": [
        "Published contacts require human review.",
        "CDN/RDAP contacts may identify a serving network rather than the origin."
      ]
    },
    "bundle": {
      "page_url": "http://127.0.0.1:9111/post/0001.html",
      "final_url": "http://127.0.0.1:9111/post/0001.html",
      "captured_at": "2026-10-10T18:52:32.472047+00:00",
      "image": {
        "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/1-a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b.image",
        "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
        "byte_length": 14213,
        "storage": "local",
        "object_key": null,
        "response_headers": {
          "server": "SimpleHTTP/0.6 Python/3.12.12",
          "date": "Sat, 10 Oct 2026 18:52:26 GMT",
          "content-type": "image/jpeg",
          "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
          "content-length": "14213"
        },
        "fetched_at": "2026-10-10T18:52:26.108781+00:00",
        "final_url": "http://127.0.0.1:9111/media/0001.jpg",
        "source": "http"
      },
      "image_sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
      "screenshot": {
        "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.png",
        "sha256": "93d0b3ff92465ba2045fb26f05e3ca2db3bf3614b0dc38eb81d2d6aa53008f8d",
        "byte_length": 91423,
        "storage": "local",
        "object_key": null
      },
      "page_response_headers": {
        "content-length": "274",
        "content-type": "text/html",
        "date": "Sat, 10 Oct 2026 18:52:32 GMT",
        "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
        "server": "SimpleHTTP/0.6 Python/3.12.12"
      },
      "requests": [
        {
          "url": "http://127.0.0.1:9111/robots.txt",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/plain",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9111/post/0001.html",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9111/post/0001.html",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "text/html",
            "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        },
        {
          "url": "http://127.0.0.1:9111/media/0001.jpg",
          "robots_allowed": true
        },
        {
          "url": "http://127.0.0.1:9111/media/0001.jpg",
          "method": "GET",
          "status": 200,
          "headers": {
            "content-type": "image/jpeg",
            "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
            "server": "SimpleHTTP/0.6 Python/3.12.12"
          }
        }
      ],
      "screenshot_url": "/api/cases/1/screenshot",
      "bundle_file": {
        "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.json",
        "sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
        "byte_length": 2582,
        "storage": "local",
        "object_key": null
      }
    },
    "next_rung": "site",
    "attestations": [
      {
        "id": 1,
        "case_id": 1,
        "question": "identity_confirmed",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424696+00:00"
      },
      {
        "id": 2,
        "case_id": 1,
        "question": "owns_photo",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424743+00:00"
      },
      {
        "id": 3,
        "case_id": 1,
        "question": "authorized_use",
        "value": {
          "answer": false
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424756+00:00"
      },
      {
        "id": 4,
        "case_id": 1,
        "question": "good_faith",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424765+00:00"
      },
      {
        "id": 5,
        "case_id": 1,
        "question": "accurate",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424772+00:00"
      },
      {
        "id": 6,
        "case_id": 1,
        "question": "authority_under_perjury",
        "value": {
          "answer": true
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424779+00:00"
      },
      {
        "id": 7,
        "case_id": 1,
        "question": "work_description",
        "value": {
          "answer": "Hypothetical local fixture original; no actual ownership claim"
        },
        "answered_by": "Demo operator",
        "answered_at": "2026-10-10T18:52:32.424786+00:00"
      }
    ],
    "notices": [],
    "deliveries": [],
    "draft_approvals": [
      {
        "id": 1,
        "case_id": 1,
        "revision": 1,
        "rung": "site",
        "approved_by": "Demo operator",
        "at": "2026-10-10T18:52:33.955800+00:00"
      }
    ],
    "timeline": [
      {
        "id": 1,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "blocked",
          "source_removed": false,
          "page_status": 200,
          "image_status": 403,
          "origin_status": null,
          "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 403,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:27.957587+00:00"
        },
        "at": "2026-10-10T18:52:27.958410+00:00"
      },
      {
        "id": 2,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "page_status": 200,
          "image_status": 503,
          "origin_status": null,
          "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 503,
              "headers": {
                "content-type": "text/html;charset=utf-8",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:28.072874+00:00"
        },
        "at": "2026-10-10T18:52:28.073549+00:00"
      },
      {
        "id": 3,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "unreachable",
          "source_removed": false,
          "error": "ReadTimeout",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "error": "ReadTimeout"
            }
          ],
          "checked_at": "2026-10-10T18:52:31.186749+00:00"
        },
        "at": "2026-10-10T18:52:31.187458+00:00"
      },
      {
        "id": 4,
        "case_id": 1,
        "kind": "verification",
        "details": {
          "outcome": "replaced",
          "source_removed": false,
          "page_status": 200,
          "image_status": 200,
          "origin_status": null,
          "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/media/0001.jpg",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "image/jpeg",
                "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "checked_at": "2026-10-10T18:52:31.346391+00:00"
        },
        "at": "2026-10-10T18:52:31.346960+00:00"
      },
      {
        "id": 5,
        "case_id": 1,
        "kind": "page_described",
        "details": {
          "status": "model_not_configured",
          "description": null,
          "advisory": true
        },
        "at": "2026-10-10T18:52:32.344307+00:00"
      },
      {
        "id": 6,
        "case_id": 1,
        "kind": "contact_saved",
        "details": {
          "contact": {
            "name": "Demo operator",
            "email": "operator@example.test",
            "address": "Local fixture address",
            "phone": "555-0100",
            "signature": "Demo operator"
          },
          "answered_by": "Demo operator",
          "revision": 1
        },
        "at": "2026-10-10T18:52:32.424803+00:00"
      },
      {
        "id": 7,
        "case_id": 1,
        "kind": "route_decided",
        "details": {
          "route": "copyright_notice",
          "rule_id": "owned_verified_same_photo",
          "version": "rules-v2",
          "inputs": {
            "answers": {
              "identity_confirmed": true,
              "owns_photo": true,
              "authorized_use": false,
              "impersonates_me": null,
              "intimate": null,
              "privacy_request": null,
              "legitimate_use": null,
              "identifiable": null,
              "good_faith": true,
              "accurate": true,
              "authority_under_perjury": true,
              "work_description": "Hypothetical local fixture original; no actual ownership claim",
              "explanation": null
            },
            "evidence": {
              "copy_relation": "exact",
              "photo_relation": "same_photo",
              "original_id": 1
            }
          },
          "revision": 1
        },
        "at": "2026-10-10T18:52:32.424824+00:00"
      },
      {
        "id": 8,
        "case_id": 1,
        "kind": "evidence_captured",
        "details": {
          "bundle": {
            "page_url": "http://127.0.0.1:9111/post/0001.html",
            "final_url": "http://127.0.0.1:9111/post/0001.html",
            "captured_at": "2026-10-10T18:52:32.472047+00:00",
            "image": {
              "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/1-a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b.image",
              "sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
              "byte_length": 14213,
              "storage": "local",
              "object_key": null,
              "response_headers": {
                "server": "SimpleHTTP/0.6 Python/3.12.12",
                "date": "Sat, 10 Oct 2026 18:52:26 GMT",
                "content-type": "image/jpeg",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "content-length": "14213"
              },
              "fetched_at": "2026-10-10T18:52:26.108781+00:00",
              "final_url": "http://127.0.0.1:9111/media/0001.jpg",
              "source": "http"
            },
            "image_sha256": "a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b",
            "screenshot": {
              "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.png",
              "sha256": "93d0b3ff92465ba2045fb26f05e3ca2db3bf3614b0dc38eb81d2d6aa53008f8d",
              "byte_length": 91423,
              "storage": "local",
              "object_key": null
            },
            "page_response_headers": {
              "content-length": "274",
              "content-type": "text/html",
              "date": "Sat, 10 Oct 2026 18:52:32 GMT",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            },
            "requests": [
              {
                "url": "http://127.0.0.1:9111/robots.txt",
                "method": "GET",
                "status": 200,
                "headers": {
                  "content-type": "text/plain",
                  "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                }
              },
              {
                "url": "http://127.0.0.1:9111/post/0001.html",
                "robots_allowed": true
              },
              {
                "url": "http://127.0.0.1:9111/post/0001.html",
                "method": "GET",
                "status": 200,
                "headers": {
                  "content-type": "text/html",
                  "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                }
              },
              {
                "url": "http://127.0.0.1:9111/media/0001.jpg",
                "robots_allowed": true
              },
              {
                "url": "http://127.0.0.1:9111/media/0001.jpg",
                "method": "GET",
                "status": 200,
                "headers": {
                  "content-type": "image/jpeg",
                  "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                }
              }
            ],
            "screenshot_url": "/api/cases/1/screenshot",
            "bundle_file": {
              "path": "people/f2bec2fa-8be0-477c-8fc2-166d962db437/evidence/case-1-47cafa8816524ca082ffa968d52a13d9.json",
              "sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
              "byte_length": 2582,
              "storage": "local",
              "object_key": null
            }
          }
        },
        "at": "2026-10-10T18:52:33.487127+00:00"
      },
      {
        "id": 9,
        "case_id": 1,
        "kind": "recipients_researched",
        "details": {
          "source": "deterministic_baseline",
          "status": "completed",
          "model_status": "model_not_configured",
          "recipients": [
            {
              "rung": "site",
              "channel": "smtp",
              "address": "agent@pixboard.test",
              "endpoint": "smtp://127.0.0.1:9118",
              "evidence": {
                "source": "http://127.0.0.1:9111/policy",
                "method": "published_email",
                "link_text": "Copyright and privacy contact"
              },
              "id": "contact-1",
              "rank": 1
            },
            {
              "rung": "search",
              "channel": "http_form",
              "address": "http://127.0.0.1:9116/report",
              "endpoint": "http://127.0.0.1:9116/report",
              "evidence": {
                "source": "platform-registry-2026-10-10",
                "method": "search_registry",
                "scope": "Delisting only; source remains"
              },
              "id": "contact-2",
              "rank": 2
            }
          ],
          "tool_calls": [
            {
              "tool": "fetch_page",
              "input": {
                "url": "http://127.0.0.1:9111/post/0001.html"
              },
              "result": {
                "status": 200,
                "final_url": "http://127.0.0.1:9111/post/0001.html",
                "title": "pixboard",
                "text": "pixboard Posted by demo-person Content policy and reports",
                "links": [
                  {
                    "url": "http://127.0.0.1:9111/policy",
                    "text": "Content policy and reports"
                  }
                ],
                "forms": [],
                "headers": {
                  "content-type": "text/html",
                  "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                },
                "contacts": []
              }
            },
            {
              "tool": "fetch_page",
              "input": {
                "url": "http://127.0.0.1:9111/post/0001.html"
              },
              "result": {
                "status": 200,
                "final_url": "http://127.0.0.1:9111/post/0001.html",
                "title": "pixboard",
                "text": "pixboard Posted by demo-person Content policy and reports",
                "links": [
                  {
                    "url": "http://127.0.0.1:9111/policy",
                    "text": "Content policy and reports"
                  }
                ],
                "forms": [],
                "headers": {
                  "content-type": "text/html",
                  "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                },
                "contacts": []
              }
            },
            {
              "tool": "find_policy_pages",
              "input": {
                "url": "http://127.0.0.1:9111/post/0001.html"
              },
              "result": {
                "status": 200,
                "source": "http://127.0.0.1:9111/post/0001.html",
                "links": [
                  {
                    "url": "http://127.0.0.1:9111/policy",
                    "text": "Content policy and reports"
                  }
                ]
              }
            },
            {
              "tool": "fetch_page",
              "input": {
                "url": "http://127.0.0.1:9111/policy"
              },
              "result": {
                "status": 200,
                "final_url": "http://127.0.0.1:9111/policy",
                "title": "",
                "text": "DMCA and privacy agent Copyright and privacy contact",
                "links": [
                  {
                    "url": "mailto:agent@pixboard.test",
                    "text": "Copyright and privacy contact"
                  }
                ],
                "forms": [],
                "headers": {
                  "content-type": "text/html",
                  "server": "SimpleHTTP/0.6 Python/3.12.12"
                },
                "contacts": [
                  {
                    "rung": "site",
                    "channel": "smtp",
                    "address": "agent@pixboard.test",
                    "endpoint": "smtp://127.0.0.1:9118",
                    "evidence": {
                      "source": "http://127.0.0.1:9111/policy",
                      "method": "published_email",
                      "link_text": "Copyright and privacy contact"
                    },
                    "id": "contact-1"
                  }
                ]
              }
            },
            {
              "tool": "dns_lookup",
              "input": {
                "hostname": "127.0.0.1"
              },
              "result": {
                "hostname": "127.0.0.1",
                "status": "resolved",
                "addresses": [
                  "127.0.0.1"
                ],
                "cnames": [],
                "caution": "DNS/CDN addresses do not prove the origin hosting provider."
              }
            },
            {
              "tool": "rdap_lookup",
              "input": {
                "ip_or_domain": "127.0.0.1"
              },
              "result": {
                "status": "completed",
                "bootstrap": "http://127.0.0.1:9117/bootstrap",
                "registry_url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
                "name": "Mock loopback allocation",
                "contacts": []
              }
            },
            {
              "tool": "platform_registry",
              "input": {
                "hostname": "127.0.0.1"
              },
              "result": {
                "version": "2026-10-10",
                "contacts": [
                  {
                    "rung": "search",
                    "channel": "http_form",
                    "address": "http://127.0.0.1:9116/report",
                    "endpoint": "http://127.0.0.1:9116/report",
                    "evidence": {
                      "source": "platform-registry-2026-10-10",
                      "method": "search_registry",
                      "scope": "Delisting only; source remains"
                    },
                    "id": "contact-2"
                  }
                ]
              }
            }
          ],
          "requests": [
            {
              "url": "http://127.0.0.1:9111/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/post/0001.html",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9111/policy",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9111/policy",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/html",
                "server": "SimpleHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9117/robots.txt",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "text/plain",
                "server": "BaseHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9117/bootstrap",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9117/bootstrap",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "application/json",
                "server": "BaseHTTP/0.6 Python/3.12.12"
              }
            },
            {
              "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
              "robots_allowed": true
            },
            {
              "url": "http://127.0.0.1:9117/ip/127.0.0.1?origin_port=9111",
              "method": "GET",
              "status": 200,
              "headers": {
                "content-type": "application/json",
                "server": "BaseHTTP/0.6 Python/3.12.12"
              }
            }
          ],
          "page_status": 200,
          "limitations": [
            "Published contacts require human review.",
            "CDN/RDAP contacts may identify a serving network rather than the origin."
          ]
        },
        "at": "2026-10-10T18:52:33.913051+00:00"
      },
      {
        "id": 10,
        "case_id": 1,
        "kind": "draft_preparation_approved",
        "details": {
          "approved_by": "Demo operator",
          "revision": 1,
          "rung": "site"
        },
        "at": "2026-10-10T18:52:33.955864+00:00"
      }
    ],
    "checks": [
      {
        "outcome": "blocked",
        "source_removed": false,
        "page_status": 200,
        "image_status": 403,
        "origin_status": null,
        "image_sha256": "edc8240a7033b7684c56984c48617895eb3241b02e6ce5422e787844bb9c9a65",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 403,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:27.957587+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "page_status": 200,
        "image_status": 503,
        "origin_status": null,
        "image_sha256": "b3bbb938ed21ec4111d5d3c3778eec50f7a5066fe16c789498c3ff7068608475",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 503,
            "headers": {
              "content-type": "text/html;charset=utf-8",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:28.072874+00:00"
      },
      {
        "outcome": "unreachable",
        "source_removed": false,
        "error": "ReadTimeout",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "error": "ReadTimeout"
          }
        ],
        "checked_at": "2026-10-10T18:52:31.186749+00:00"
      },
      {
        "outcome": "replaced",
        "source_removed": false,
        "page_status": 200,
        "image_status": 200,
        "origin_status": null,
        "image_sha256": "0c2094c50600d8677dfd68fce69c2c788a2a910b62c81da902a7d152039418fd",
        "requests": [
          {
            "url": "http://127.0.0.1:9111/robots.txt",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/plain",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/post/0001.html",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "text/html",
              "last-modified": "Sat, 10 Oct 2026 18:52:22 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "robots_allowed": true
          },
          {
            "url": "http://127.0.0.1:9111/media/0001.jpg",
            "method": "GET",
            "status": 200,
            "headers": {
              "content-type": "image/jpeg",
              "last-modified": "Sat, 10 Oct 2026 18:52:31 GMT",
              "server": "SimpleHTTP/0.6 Python/3.12.12"
            }
          }
        ],
        "checked_at": "2026-10-10T18:52:31.346391+00:00"
      }
    ],
    "clock": "2026-10-10T18:52:33.958376+00:00",
    "demo_clock": true
  }
}
```

### POST /api/cases/1/draft (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"recipient_id": "contact-1", "rung": "site"}' http://127.0.0.1:8190/api/cases/1/draft
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/draft",
  "request": {
    "json": {
      "recipient_id": "contact-1",
      "rung": "site"
    }
  },
  "status": 200,
  "response": {
    "id": 1,
    "case_id": 1,
    "revision": 1,
    "rung": "site",
    "recipient": {
      "rung": "site",
      "channel": "smtp",
      "address": "agent@pixboard.test",
      "endpoint": "smtp://127.0.0.1:9118",
      "evidence": {
        "source": "http://127.0.0.1:9111/policy",
        "method": "published_email",
        "link_text": "Copyright and privacy contact"
      },
      "id": "contact-1",
      "rank": 1
    },
    "payload": {
      "route": "copyright_notice",
      "rung": "site",
      "page_url": "http://127.0.0.1:9111/post/0001.html",
      "image_url": "http://127.0.0.1:9111/media/0001.jpg",
      "facts": {
        "identity_confirmed": true,
        "owns_photo": true,
        "authorized_use": false,
        "impersonates_me": null,
        "intimate": null,
        "privacy_request": null,
        "legitimate_use": null,
        "identifiable": null,
        "good_faith": true,
        "accurate": true,
        "authority_under_perjury": true,
        "work_description": "Hypothetical local fixture original; no actual ownership claim",
        "explanation": null
      },
      "contact": {
        "name": "Demo operator",
        "email": "operator@example.test",
        "address": "Local fixture address",
        "phone": "555-0100",
        "signature": "Demo operator"
      },
      "body": "Removal request: copyright_notice\nDate: 2026-10-10T18:52:33.989619+00:00\nPage: http://127.0.0.1:9111/post/0001.html\nImage: http://127.0.0.1:9111/media/0001.jpg\nCopyrighted work: Hypothetical local fixture original; no actual ownership claim\nProtected original SHA256: a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b\nI have a good faith belief that the use complained of is not authorized by the copyright owner, its agent, or the law.\nThe information in this notice is accurate. Under penalty of perjury, I am authorized to act on behalf of the owner of the exclusive right allegedly infringed.\nPlease remove or disable access to the identified material under 17 U.S.C. 512(c)(3).\nPerson's explanation: \nName: Demo operator\nEmail: operator@example.test\nAddress: Local fixture address\nPhone: 555-0100\nElectronic signature: Demo operator",
      "template": "copyright_notice-v2",
      "bundle_sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
      "recipient": {
        "rung": "site",
        "channel": "smtp",
        "address": "agent@pixboard.test",
        "endpoint": "smtp://127.0.0.1:9118",
        "evidence": {
          "source": "http://127.0.0.1:9111/policy",
          "method": "published_email",
          "link_text": "Copyright and privacy contact"
        },
        "id": "contact-1",
        "rank": 1
      }
    },
    "sha256": "c80f107bd5a70478d6acec9939db0d86a25bd73ca6dfa1a883c11f69a32405ca",
    "created_at": "2026-10-10T18:52:33.989682+00:00",
    "approved_by": null,
    "approved_at": null
  }
}
```

### POST /api/cases/1/approve (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"notice_id": 1, "sha256": "c80f107bd5a70478d6acec9939db0d86a25bd73ca6dfa1a883c11f69a32405ca", "approved_by": "Demo operator"}' http://127.0.0.1:8190/api/cases/1/approve
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/approve",
  "request": {
    "json": {
      "notice_id": 1,
      "sha256": "c80f107bd5a70478d6acec9939db0d86a25bd73ca6dfa1a883c11f69a32405ca",
      "approved_by": "Demo operator"
    }
  },
  "status": 200,
  "response": {
    "id": 1,
    "case_id": 1,
    "revision": 1,
    "rung": "site",
    "recipient": {
      "rung": "site",
      "channel": "smtp",
      "address": "agent@pixboard.test",
      "endpoint": "smtp://127.0.0.1:9118",
      "evidence": {
        "source": "http://127.0.0.1:9111/policy",
        "method": "published_email",
        "link_text": "Copyright and privacy contact"
      },
      "id": "contact-1",
      "rank": 1
    },
    "payload": {
      "route": "copyright_notice",
      "rung": "site",
      "page_url": "http://127.0.0.1:9111/post/0001.html",
      "image_url": "http://127.0.0.1:9111/media/0001.jpg",
      "facts": {
        "identity_confirmed": true,
        "owns_photo": true,
        "authorized_use": false,
        "impersonates_me": null,
        "intimate": null,
        "privacy_request": null,
        "legitimate_use": null,
        "identifiable": null,
        "good_faith": true,
        "accurate": true,
        "authority_under_perjury": true,
        "work_description": "Hypothetical local fixture original; no actual ownership claim",
        "explanation": null
      },
      "contact": {
        "name": "Demo operator",
        "email": "operator@example.test",
        "address": "Local fixture address",
        "phone": "555-0100",
        "signature": "Demo operator"
      },
      "body": "Removal request: copyright_notice\nDate: 2026-10-10T18:52:33.989619+00:00\nPage: http://127.0.0.1:9111/post/0001.html\nImage: http://127.0.0.1:9111/media/0001.jpg\nCopyrighted work: Hypothetical local fixture original; no actual ownership claim\nProtected original SHA256: a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b\nI have a good faith belief that the use complained of is not authorized by the copyright owner, its agent, or the law.\nThe information in this notice is accurate. Under penalty of perjury, I am authorized to act on behalf of the owner of the exclusive right allegedly infringed.\nPlease remove or disable access to the identified material under 17 U.S.C. 512(c)(3).\nPerson's explanation: \nName: Demo operator\nEmail: operator@example.test\nAddress: Local fixture address\nPhone: 555-0100\nElectronic signature: Demo operator",
      "template": "copyright_notice-v2",
      "bundle_sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
      "recipient": {
        "rung": "site",
        "channel": "smtp",
        "address": "agent@pixboard.test",
        "endpoint": "smtp://127.0.0.1:9118",
        "evidence": {
          "source": "http://127.0.0.1:9111/policy",
          "method": "published_email",
          "link_text": "Copyright and privacy contact"
        },
        "id": "contact-1",
        "rank": 1
      }
    },
    "sha256": "c80f107bd5a70478d6acec9939db0d86a25bd73ca6dfa1a883c11f69a32405ca",
    "created_at": "2026-10-10T18:52:33.989682+00:00",
    "approved_by": "Demo operator",
    "approved_at": "2026-10-10T18:52:34.306980+00:00"
  }
}
```

### POST /api/cases/1/send (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/cases/1/send
```

```json
{
  "method": "POST",
  "path": "/api/cases/1/send",
  "request": {},
  "status": 200,
  "response": {
    "id": 1,
    "case_id": 1,
    "notice_id": 1,
    "rung": "site",
    "status": "acted",
    "response": {
      "status": "acted",
      "transport": "smtp",
      "code": 250,
      "reply": {
        "id": 1,
        "route": "copyright_notice",
        "page_url": "http://127.0.0.1:9111/post/0001.html",
        "image_url": "http://127.0.0.1:9111/media/0001.jpg",
        "received_at": 1791658354.570536,
        "status": "acted"
      }
    },
    "sent_at": "2026-10-10T18:52:34.440192+00:00",
    "deadline": "2026-10-12T18:52:34.440205+00:00",
    "processed": true
  }
}
```

### POST /api/clock/advance (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"seconds": 172801}' http://127.0.0.1:8190/api/clock/advance
```

```json
{
  "method": "POST",
  "path": "/api/clock/advance",
  "request": {
    "json": {
      "seconds": 172801
    }
  },
  "status": 200,
  "response": {
    "now": "2026-10-12T18:52:35.855234+00:00",
    "ticks": []
  }
}
```

### GET /api/cases/2/route (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/2/route
```

```json
{
  "method": "GET",
  "path": "/api/cases/2/route",
  "request": {},
  "status": 200,
  "response": {
    "route": "impersonation_report",
    "rule_id": "attested_impersonation",
    "version": "rules-v2",
    "inputs": {
      "answers": {
        "identity_confirmed": true,
        "owns_photo": null,
        "authorized_use": false,
        "impersonates_me": true,
        "intimate": null,
        "privacy_request": null,
        "legitimate_use": null,
        "identifiable": null,
        "good_faith": true,
        "accurate": true,
        "authority_under_perjury": true,
        "work_description": "Hypothetical local fixture original; no actual ownership claim",
        "explanation": null
      },
      "evidence": {
        "copy_relation": "none",
        "photo_relation": "different_photo",
        "original_id": null
      }
    }
  }
}
```

### GET /api/cases/2/screenshot (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/2/screenshot
```

```json
{
  "method": "GET",
  "path": "/api/cases/2/screenshot",
  "request": {},
  "status": 200,
  "response": {
    "content_type": "image/png",
    "byte_length": 97633,
    "sha256": "767d3ac68b42020f09e3c35b37d42b7a71b30807e8c25d5518ed370534506556"
  }
}
```

### POST /api/cases/3/approve-draft (HTTP 422)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"approved_by": "Demo operator", "revision": 1}' http://127.0.0.1:8190/api/cases/3/approve-draft
```

```json
{
  "method": "POST",
  "path": "/api/cases/3/approve-draft",
  "request": {
    "json": {
      "approved_by": "Demo operator",
      "revision": 1
    }
  },
  "status": 422,
  "response": {
    "error": {
      "code": "validation_error",
      "message": "This route cannot be approved for drafting"
    }
  }
}
```

### POST /api/scheduler/tick (HTTP 200)

```sh
curl -sS -X POST http://127.0.0.1:8190/api/scheduler/tick
```

```json
{
  "method": "POST",
  "path": "/api/scheduler/tick",
  "request": {},
  "status": 200,
  "response": []
}
```

### POST /api/cases/6/reply-analysis (HTTP 200)

```sh
curl -sS -X POST -H 'Content-Type: application/json' --data '{"text": "Licensed editorial use"}' http://127.0.0.1:8190/api/cases/6/reply-analysis
```

```json
{
  "method": "POST",
  "path": "/api/cases/6/reply-analysis",
  "request": {
    "json": {
      "text": "Licensed editorial use"
    }
  },
  "status": 200,
  "response": {
    "status": "model_not_configured",
    "category": null,
    "recommendation": null,
    "advisory": true
  }
}
```

### GET /api/cases/1/draft (HTTP 200)

```sh
curl -sS -X GET http://127.0.0.1:8190/api/cases/1/draft
```

```json
{
  "method": "GET",
  "path": "/api/cases/1/draft",
  "request": {},
  "status": 200,
  "response": {
    "id": 1,
    "case_id": 1,
    "revision": 1,
    "rung": "site",
    "recipient": {
      "rung": "site",
      "channel": "smtp",
      "address": "agent@pixboard.test",
      "endpoint": "smtp://127.0.0.1:9118",
      "evidence": {
        "source": "http://127.0.0.1:9111/policy",
        "method": "published_email",
        "link_text": "Copyright and privacy contact"
      },
      "id": "contact-1",
      "rank": 1
    },
    "payload": {
      "route": "copyright_notice",
      "rung": "site",
      "page_url": "http://127.0.0.1:9111/post/0001.html",
      "image_url": "http://127.0.0.1:9111/media/0001.jpg",
      "facts": {
        "identity_confirmed": true,
        "owns_photo": true,
        "authorized_use": false,
        "impersonates_me": null,
        "intimate": null,
        "privacy_request": null,
        "legitimate_use": null,
        "identifiable": null,
        "good_faith": true,
        "accurate": true,
        "authority_under_perjury": true,
        "work_description": "Hypothetical local fixture original; no actual ownership claim",
        "explanation": null
      },
      "contact": {
        "name": "Demo operator",
        "email": "operator@example.test",
        "address": "Local fixture address",
        "phone": "555-0100",
        "signature": "Demo operator"
      },
      "body": "Removal request: copyright_notice\nDate: 2026-10-10T18:52:33.989619+00:00\nPage: http://127.0.0.1:9111/post/0001.html\nImage: http://127.0.0.1:9111/media/0001.jpg\nCopyrighted work: Hypothetical local fixture original; no actual ownership claim\nProtected original SHA256: a4ee939875796a2e4bc45e788072cb1066b033708817bdcec2a3effe5a5daa3b\nI have a good faith belief that the use complained of is not authorized by the copyright owner, its agent, or the law.\nThe information in this notice is accurate. Under penalty of perjury, I am authorized to act on behalf of the owner of the exclusive right allegedly infringed.\nPlease remove or disable access to the identified material under 17 U.S.C. 512(c)(3).\nPerson's explanation: \nName: Demo operator\nEmail: operator@example.test\nAddress: Local fixture address\nPhone: 555-0100\nElectronic signature: Demo operator",
      "template": "copyright_notice-v2",
      "bundle_sha256": "0be169ae545593478d5eef1cd6946de390305aa55f7825efb2e6f58ddb708c42",
      "recipient": {
        "rung": "site",
        "channel": "smtp",
        "address": "agent@pixboard.test",
        "endpoint": "smtp://127.0.0.1:9118",
        "evidence": {
          "source": "http://127.0.0.1:9111/policy",
          "method": "published_email",
          "link_text": "Copyright and privacy contact"
        },
        "id": "contact-1",
        "rank": 1
      }
    },
    "sha256": "c80f107bd5a70478d6acec9939db0d86a25bd73ca6dfa1a883c11f69a32405ca",
    "created_at": "2026-10-10T18:52:33.989682+00:00",
    "approved_by": "Demo operator",
    "approved_at": "2026-10-10T18:52:34.306980+00:00"
  }
}
```
