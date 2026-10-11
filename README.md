# CenSearch

Find where your face and photos appear, select the matches, and authorize an
agent to work through removal requests. CenSearch chooses a route, finds a
recipient, sends a fixed-template notice when delivery is available, and checks
whether the image is still there. Every decision and notice stays visible.

**[Hosted app](https://172.237.143.49.sslip.io/app/)** ·
**[46-second interface walkthrough](docs/interface-walkthrough.mp4)**

The hosted app requires the team's shared access password. The recording uses
clearly labelled sample data and placeholder images: it demonstrates selection,
authorization, outcome review and settings, with no search or email delivery.
For a password-free local preview, see below.

## The product loop

1. **Enroll.** Add face photos and any originals you own. Settings → Profile
   shows enrollment details and saved photos, with upload and removal controls.
   At least one face photo must remain. Deleting an original also deletes its
   linked matches and request records.
2. **Find.** Search by face, name/handle, or supplied page URLs. FaceCheck requires
   explicit consent to upload the first enrolled face photo and spend three
   credits. Only provider scores strictly above 90 appear. Provider candidates
   remain distinguishable from locally verified face/copy matches; a provider
   score is not proof of identity, misuse or copyright ownership.
3. **Decide.** Select matches and accept responsibility for the batch. Strands
   chooses a copyright notice, impersonation report, intimate-image report,
   voluntary privacy request, leave-alone decision, or hold for review.
4. **Send.** The default is automatic sending after authorization. Optional
   **Review notices before sending** pauses at the exact drafts. Resend sends
   configured email; missing setup leaves drafts. Website forms remain manual.
5. **Verify.** Recheck a page and distinguish removal from a blocked or uncertain
   fetch. A still-present image can become eligible for site → host → search
   engine follow-up. Each follow-up requires new approval; a reasoned refusal
   does not trigger automatic escalation.

Whitelist entries apply to a domain and its subdomains. The current list blocks
new drafts and deliveries, including individual actions. It cannot recall a
request already sent. Saved FaceCheck scans can be reopened without another
upload or charge, or deleted independently of enrollment and notice history.

## Strands and Akamai

Strands owns the decisions that require reading unfamiliar pages: route choice,
recipient research, page context and reply classification. Its recipient tools
fetch pages with a request budget, inspect policy/contact pages, and query DNS,
RDAP and platform records. Each proposed recipient includes its evidence.
The agent receives page text and URLs, never face photos, and never writes the
legal wording: notices come from fixed templates. Without a model, supported
operations use an explicitly labelled rule fallback.

| Layer | Implementation |
| --- | --- |
| Agent inference | Strands Agents SDK → Akamai's OpenAI-compatible inference, `hackathon-chat` |
| Hosting | One Akamai/Linode instance in Chicago, Docker Compose, Caddy HTTPS |
| API and data | Python 3.12, FastAPI, SQLite and SQLAlchemy |
| Face/copy verification | OpenCV YuNet + SFace on the app host; perceptual hash, SIFT + RANSAC |
| Discovery and capture | FaceCheck; optional SerpApi text search; httpx and Playwright |
| Evidence | Local storage plus optional Akamai Object Storage |
| Frontend | React, TypeScript, Vite; shadcn/ui, Radix, Tailwind and Lucide |
| Email | Resend; separate loopback SMTP/HTTP mock sites for local testing |

![System architecture](docs/architecture.png)

## What has been verified

The local checkout and hosted build are different versions. These observations
are dated **2026-10-11 UTC**, not continuous monitoring.

| Check | Evidence and boundary |
| --- | --- |
| Current backend | 272 tests passed in 32.63 seconds using local-only fixtures |
| Current frontends | Product build/lint and operator-console build passed |
| Local end-to-end | Built signup → two matched URLs → reviewed mock send → removal check → approved host follow-up passed in 16.71 seconds; no external calls |
| Profile and whitelist | Real local API browser check passed photo persistence, upload/removal gates, domain/subdomain exclusion, reload, keyboard and 360–1440px layouts |
| Hosted app, fresh health read | SQLite healthy, face models loaded, model configured; public HTTPS returned 401 as expected without the password |
| Hosted Strands inference | Earlier saved deployment validation completed a live DNS tool call; current health retains `live_call_verified: true` |
| Akamai Object Storage | Earlier saved deployment validation recorded synthetic text write/read/delete; current process health reports `remote_verified: false` |
| Resend demo | Saved report records one API-accepted email and a provider `delivered` event for Resend's **simulated test recipient**; no real inbox delivery or takedown is established |

The hosted build still has external delivery and public crawling disabled in
its health response and predates the current email/profile changes. Hosted
owner-face acceptance, production email to a controlled real recipient, and a
real-site removal remain unverified. A saved local CLI FaceCheck run returned
197 candidates; that is not 197 verified matches or a hosted-app acceptance run.
Name/handle search also needs a SerpApi key, absent in the last deployment check.

Local browser/API checks and their scope are recorded in
[verification.json](docs/verification.json). The interface video uses simulated
outcomes; it is not evidence of the model, crawler or delivery provider running.

## Run locally

Install Python 3.12, `uv` and Node.js. From the repository root:

```sh
git clone https://github.com/njiedev/CenSearch.git
cd CenSearch
make -C backend setup
cp -n backend/.env.example backend/.env
make -C backend api
```

`setup` installs dependencies, face models, Chromium and both frontend builds.
It does not download face datasets. Preserve any existing `.env`.
Open [the local dashboard](http://127.0.0.1:8190/app/) or
[the sample interface](http://127.0.0.1:8190/app/?sample=1), which needs no provider
keys and performs no real search or delivery. Enrollment is at `/signup.html`;
the operator console is at `/console/`.

For frontend development, run `npm --prefix frontend run dev` in a second shell.
Vite proxies `/api` to port 8190. Rebuild with `npm --prefix frontend run build`
when using the static frontend served by FastAPI.

### Optional providers

Store credentials only in the ignored `backend/.env`, never frontend variables.
The example file lists all settings.

- **Model:** `MODEL_PROVIDER=openai_compatible`,
  `OPENAI_BASE_URL=https://ws.akamai-workshops.com/v1`,
  `CHAT_MODEL=hackathon-chat`, and `OPENAI_API_KEY`.
- **Text search:** `SERPAPI_API_KEY`. Supplied URLs work without it. Each public
  scan requires explicit permission to fetch public pages.
- **Face search:** `FACECHECK_API_TOKEN`. Use the owner's own face while present;
  never upload dataset/fixture people. In `backend/`,
  `uv run python scripts/facecheck.py --info` checks the account without a search.
  The CLI supports explicit upload consent and resuming an existing search ID.
- **Object Storage:** `OBJ_ENDPOINT`, `OBJ_BUCKET`, `OBJ_ACCESS_KEY`,
  `OBJ_SECRET_KEY`. Local storage works without these.
- **Email:** a verified Resend sending domain, `RESEND_API_KEY`,
  `CENSEARCH_EMAIL_FROM` (a bare sender address), and
  `CENSEARCH_EMAIL_ENABLED=true`. Restart, then check `/api/health` →
  `email_delivery.ready`; that flag checks configuration, not live delivery.

Resend receives the fixed notice text, subject and addresses, with no photo or
evidence attachments. The batch contact email becomes Reply-To. Provider
acceptance is recorded with a message ID and means awaiting a response, not
inbox delivery or removal. Uncertain timeouts are not automatically retried;
persistent deduplication and provider idempotency keys guard against duplicates.
Inbox synchronization and bounce webhooks are not implemented.

### Local mock demo

Supply authorized local fixtures arranged as
`<person>/{reference,originals,wild}/*.jpg` (optionally under `people/`).

```sh
make -C backend demo PHOTOS=/absolute/path/to/fixtures
# Optional hosted inference for page text only:
make -C backend demo PHOTOS=/absolute/path/to/fixtures MODEL=1
```

The launcher prints its URLs, enables an accelerated demo clock, and stops its
servers on Ctrl-C. Mock sites act as independent administrators over HTTP/SMTP.
The backend never reads their ground truth. Fixtures stay local. Override
`API_PORT` and `BASE_PORT` if the defaults are occupied.

For the three-match agent scenario, configure the model and run:

```sh
make -C backend demo-three PHOTOS=/absolute/path/to/fixtures
# Opt in to a real Resend API call to its simulated test recipient:
make -C backend demo-three PHOTOS=/absolute/path/to/fixtures RESEND=1
```

This scenario presents unauthorized resale, licensed exhibition and disputed
rights. Decisions come from the agent. The opt-in relay sends fictional notice
text with a demo disclaimer from `onboarding@resend.dev` to
`delivered+censearch-demo@resend.dev`. No photos leave the machine. Provider logs
are real but delivery events are simulated; pages stay unchanged in this mode.
Regular fixtures cannot send real email to real recipients. Test submissions
consume Resend quota. Without `RESEND=1`, delivery stays within the local mock.

### Checks and deployment

```sh
LIKENESS_TEST_PHOTOS=/absolute/path/to/fixtures make -C backend test
npm --prefix frontend run build
npm --prefix frontend run lint
npm --prefix backend/demo-ui run build
backend/.venv/bin/python frontend/tests/profile_browser.py
make -C backend e2e-app PHOTOS=/absolute/path/to/fixtures
```

The profile check uses synthetic face-free images and a disposable real API.
The end-to-end check uses local fixture enrollment, actual crawling, mock
HTTP/SMTP delivery, removal verification and approved host follow-up, with no
intercepted API responses or external calls.

`bash backend/deploy/package.sh /tmp/censearch.tar.gz` creates an allowlisted source
archive. It excludes credentials, local photos/fixtures and runtime data. The
Docker build uses the eye graphic for decorative sample images. A cloud update
is a separate explicit operation via `backend/deploy/deploy.sh`; persistent data
stays in its volume behind Caddy access protection.

## Privacy and limits

Face matching runs on the app host. Only consented FaceCheck discovery uploads
the selected face photo to that provider. Small thumbnails and heavy occlusion
can defeat face matching; copy detection helps only when an original is enrolled.
A different photo of the same person does not support a copyright claim.
Provider candidates and failed fetches require care, not automatic certainty.
The person accepts responsibility for each batch's statements.

This is a hackathon build with shared deployment access, not a multi-tenant
account service. The live owner-face demonstration and real recipient delivery
are acceptance work still to finish. The repo includes the licenses for bundled
fonts and UI components; Cuelume supplies synthesized browser interface sounds.
