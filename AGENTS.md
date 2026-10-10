# AGENTS.md — Likeness Guard

Read this before writing any code. It records what the project is, how it is
meant to be built, and what the owner cares about. Where this file and your
instincts disagree, this file wins; where the owner and this file disagree, the
owner wins.

## What the project is

Likeness Guard finds where a person's face and photos appear on the web, works
out which removal process applies to each appearance, sends the request to the
right recipient, and checks whether it worked.

The loop, end to end:

1. **Enrol** — the person adds a few photos of their face and any original
   photos they own.
2. **Find** — search and crawl for pages showing that face or copies of those
   photos.
3. **Decide** — for each appearance, the person answers a short set of
   questions; fixed rules pick the route (copyright notice, impersonation
   report, intimate-image report, plain privacy request, leave alone, or hold
   for review).
4. **Send** — an agent works out who receives the request (site, then host,
   then search engine) and the request is drafted from a fixed template.
5. **Verify** — re-check the page later; escalate up the ladder if nothing
   changed.

The pitch line: **the agent does the legwork but never swears to anything.**
The person attests to the facts, rules pick the route, the agent does the
open-ended research around it.

## Goal

Win, or place in, two sponsor tracks at a 24-hour hackathon:

- **Best Use of Strands Agents SDK** — judged on (1) does it integrate Strands,
  (2) is the use unique or creative. This is our better shot.
- **Akamai Cloud** — judged on impact, use of Akamai resources and/or their
  hosted inference, technical execution (does it work, is it stable), and
  creativity.

The deliverable is a **live demo on the owner's own face**, running on Akamai,
that a judge can follow in under three minutes. Everything else is secondary.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language / env | Python 3.12, `uv` | Pin versions. |
| API | FastAPI + uvicorn | |
| Agent | Strands Agents SDK (`strands-agents`, `strands-agents-tools`) | Tools are plain Python functions with `@tool`. |
| Model | Akamai hosted inference, called from Strands | Endpoint, models and credentials arrive at kickoff. Expected to be OpenAI-compatible (use Strands' OpenAI model provider with a custom base URL) — **confirm at kickoff**. Keep the model provider behind one config value so we can switch to our own inference. |
| Face matching | OpenCV YuNet (detect) + SFace (embed), run locally | Pretrained models with published accuracy; use them as-is, no benchmark work. |
| Copy detection | Perceptual hash, then SIFT + RANSAC | Catches thumbnails and occluded faces that face matching misses. |
| Crawl / capture | httpx + Playwright (Chromium) | Playwright for script-rendered pages and evidence screenshots. |
| Data | SQLite + SQLAlchemy | Managed database on Akamai is a stretch goal only. |
| Evidence storage | Akamai Object Storage (S3-compatible) | Screenshots and evidence bundles. |
| Hosting | One Akamai (Linode) compute instance | Backend, crawler, face matching and frontend on the same box. No Kubernetes. |
| Frontend | React + Vite + TypeScript, built to static files served by FastAPI | One deploy, no separate frontend host. |
| Live face search | FaceCheck API (stretch, see constraints) | About $0.30 per search; crypto-only payment; small packs expire in 2 days; terms say personal, non-commercial use. |

Out of the stack: government ID checks (Login.gov and ID.me are closed to us;
Stripe Identity is possible but out of scope), any second agent framework, any
vector database.

## Where the agent goes — and where it does not

**Agent (Strands) owns:**

- **Recipient lookup.** Given a page URL, find who to send a removal request
  to. Tools: fetch a page (robots-aware, with a request budget), find and read
  the policy/contact page, DNS lookup, registry record lookup (RDAP), platform
  registry lookup. Output: a ranked list of contacts with the evidence for
  each. This must work on real sites it has never seen.
- **Reading replies.** Classify a reply as acted, reasoned refusal, brush-off,
  or needs more information, and recommend the next step.
- **Describing the page.** Tell the person what the page looks like (news
  article, profile, repost, gallery) before they answer the questions.

**Agent never:**

- picks the legal route,
- fills in or implies any attested fact (ownership, consent, identity),
- writes the legal text of a notice,
- sends anything without the person approving that specific request.

Route selection stays a pure function of the person's answers plus match
evidence. Notices stay fixed templates. Face photos are never sent to the
model; it sees page text and URLs only.

## Design decisions

- **Fixed rules for the route, human attestations for the facts.** It is both
  the safe design and the differentiator.
- **A delivery gate** that only allows sending to loopback addresses unless an
  explicit flag is set. Default off.
- **Mock sites act as independent administrators**, reachable only over HTTP
  and mail, with a ground-truth file the backend never reads. The score comes
  from comparing the two.
- **An injectable clock** so a two-day wait can be shown in seconds.
- **An escalation ladder:** site → host → search engine.
- **Evidence capture** (screenshot plus a bundle) before any request is
  drafted.
- **Face matching runs locally**, not through a cloud face service.

## Pitfalls to avoid

- **Backend first, no screen.** Build the thinnest end-to-end slice with a
  screen first, so there is always something a judge can look at.
- **A demo only on our own fake sites.** "Our system beats sites we wrote" does
  not win. The owner's real face on the real web must be in the demo.
- **Recipient lookup tied to conventions only the mock sites use** (custom meta
  tags, custom link relations, made-up headers). Write it against real sites
  first, mocks second.
- **Loose page heuristics**, such as treating any page containing the word
  "report" as a reporting form.
- **Automatic escalation after a reasoned refusal.** A site answering "licensed
  editorial use" is not the same as a site ignoring us.
- **Slow checks.** Nothing in the normal build-and-test loop should take more
  than a minute or two.
- **Dense one-line code** (many statements per line joined with semicolons).
  Write normal, readable Python.
- **Scenarios that cannot fail.** Each test scenario must be able to fail for a
  real reason, or the pass count means nothing.

**Known limits of the approach — design around them, do not try to fix them:**

- Faces in small thumbnails and heavily occluded faces are missed by face
  matching; copy detection covers them only when we hold the original photo.
- Same-person-different-photo matches are a privacy request at most, never a
  copyright claim.

## Scope for 24 hours

**Must have (in this order):**

1. Deployed skeleton on Akamai: backend, one screen, model call through Strands
   working.
2. Enrol from webcam or upload.
3. Find and match against a small mock web (two or three sites).
4. Question screen → route → drafted request.
5. Strands recipient-lookup agent, shown working on a real domain (read-only)
   and on a mock site.
6. Send to a mock site, verify, show one escalation with the clock advanced.
7. Live search on the owner's own face, results shown in the same screen.

**Stretch:** reply-reading agent, managed database, re-upload detection, a
second enrolled person.

**Out:** real submission of notices to real sites, government ID checks,
accounts and login, payments, mobile, browser extension, any benchmark work.

For real sites the product stops at a drafted request and a named recipient;
the person sends it themselves.

## Hard constraints

- **Nothing is submitted to a real site.** Emails and form posts go to loopback
  mock hosts only. Read-only DNS, registry lookups and public page fetches on
  real domains are fine in small volume, respecting robots.txt.
- **No face photo of a dataset or fixture person goes to any third party** —
  not FaceCheck, not a cloud vision API, not the model. Live search is used
  only on the owner's own face, with the owner present.
- **The owner's email address is for attribution only.** Never put it in a
  request to an unrelated service.
- **Never ask for secrets in chat.** Use the secret-request tool.
- **Never tune against the mock ground truth.** The backend must not read it.
- **Ask the owner before the first git commit.**

## What the owner cares about

- **Brutal honesty.** Say what does not work, what was skipped and what is
  faked. Never report a pass you did not run.
- **A demo that is real.** Their own face, a real search, a real recipient
  found on a real domain.
- **Short, plain answers.** Casual tone is fine; padding is not.
- **Privacy taken seriously.** This project handles faces; act like it.
- **Not wasting the clock.** Prefer the boring choice that works over the
  clever one that might.

## Working with agents on this repo

- When delegating to Codex Astra, use `high` reasoning effort for substantial
  build rounds and `medium` for small fix or review rounds. Never `xhigh`
  unless the owner asks.
- A delegated round ends with: what changed, what was run, the actual output,
  and what was not done.
- Leave no servers or listeners running at the end of a round.
