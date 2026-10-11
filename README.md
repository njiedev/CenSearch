# CenSearch: autonomous takedowns for your face

Find where your face and photos appear on the web, and get them taken down:

1. **Select your matches**: CenSearch searches public pages by your name and
   handles, checks any page URLs you give it, and matches your face and copies
   of photos you own on what it finds.
2. **Click once**: a Strands agent picks the legal route for each match, finds
   who to send the request to, drafts it from a fixed template and sends it.
3. **It checks back**: the page is re-checked later, and the request escalates
   from the site to its host to the search engine if nothing changed.

Built in 24 hours at **Hack Midwest 2026** (Kansas City) for the AWS *Best Use
of Strands Agents SDK* and *Akamai Cloud AI* challenges.

> Hackathon project. Parts marked *in progress* aren't finished, and the
> "What is real and what is simulated" section below says plainly which parts
> of the demo are mocked.

## Demo

*In progress: demo video and screenshots go here.*

## Overview

The project is organized into two folders:

1. `backend`: FastAPI service with the crawler, local face and copy matching,
   the Strands agents, notice templates, delivery, verification, and the mock
   sites used for the send step. It also holds `demo-ui`, the operator console.
2. `frontend`: the public landing and sign-up pages (React, Vite, TypeScript).

The public pages use Cuelume 0.1.2 for interface sounds: ticks on link hover,
a page cue on links, clicks on buttons, and a soft bloom on accordions. These are synthesized in
the browser with Web Audio, with no audio downloads or external requests.
Sound starts after a user gesture. The Sound control remembers mute locally;
reduced-motion visitors also skip hover sounds. Cuelume is MIT licensed.

### How it works

1. **Enroll:** add a few photos of your face and any original photos you own.
2. **Find:** the agent proposes search queries from your name, handles and
   context, runs them through a search API, and the result pages are fetched
   and matched. You can also paste page URLs to check directly. Matching runs
   locally with OpenCV YuNet and SFace, plus perceptual hashing and SIFT for
   copies.
3. **Decide:** the agent picks the route for each match (copyright notice,
   impersonation report, intimate-image report, privacy request, leave alone,
   or hold for review) and shows why.
4. **Send:** the agent finds the recipient (site, then host, then search
   engine) from the page, DNS and registry records, and sends the drafted
   request. You accept a legal-responsibility warning before each batch.
5. **Verify:** the page is re-checked; silence escalates up the ladder, a
   reasoned refusal does not.

### Architecture

![CenSearch system diagram](docs/architecture.png)

## Quick Start

You need Python 3.12 with `uv`, and Node for the two UIs.

**1. Install dependencies**

```bash
git clone <this repo>
cd censearch

# Backend: Python packages, face models, Chromium, operator console
cd backend
make setup

cd ..

# Landing and sign-up pages
cd frontend
npm install
```

**2. Provide your model key**

Copy `backend/.env.example` to `backend/.env` and fill in the model settings.
Any OpenAI-compatible endpoint works; we use Akamai's hosted inference.

```bash
MODEL_PROVIDER=...
OPENAI_BASE_URL=...
OPENAI_API_KEY=...
CHAT_MODEL=...
```

Without a model, routing and search-query building fall back to labelled
rule-based versions.

For the name and handle search, add a SerpApi key. Checking pasted URLs works
without one.

```bash
SERPAPI_API_KEY=...
```

**3. Launch**

```bash
# Full demo: API, mock sites and the console, seeded from a folder of photos
cd backend
make demo PHOTOS=/path/to/photos

# Or the pieces separately
make api            # API on http://127.0.0.1:8190
cd ../frontend
npm run dev         # landing page on http://localhost:5173, proxies /api to 8190
```

**4. Run the checks**

```bash
cd backend
make test
```

## Why CenSearch?

#### 1. Anyone can film you now

Camera glasses and phone cameras put strangers' faces online every day, and
getting a photo removed means working out which process applies, who to
contact, and following up when nobody answers. Most people give up.

#### 2. An agent that does the legwork

The Strands agent reads the page, picks the route, finds the right recipient
on sites it has never seen, and sends the request. Every route, reason,
recipient and notice is shown afterwards; nothing is hidden.

#### 3. Privacy taken seriously

- Face matching runs locally, not through a cloud face service.
- Face photos are never sent to the language model; it sees page text and
  URLs only.
- The legal text of a notice is a fixed template. The agent never writes it.

## What is real and what is simulated

- **Real:** enrollment, crawling, local face and copy matching, the agent's
  route choice, and recipient lookup on real domains (read-only).
- **Simulated:** sending. Requests go only to mock sites on the same machine,
  which act as independent administrators. For real sites the product stops
  at a drafted request and a named recipient.
- **Built, not yet run live:** search of the real public web seeded by your
  name and handles, and the "check these URLs" mode. Both pass their tests
  against mock pages and synthetic search responses. This is a name-seeded
  search, not a face index: it only finds pages a text search can reach.
