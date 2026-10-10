# CenSearch

CenSearch finds where your face and photos appear on the web, works out which
removal process applies to each appearance, sends the request to the right
recipient, and checks whether it worked.

**The agent does the legwork but never swears to anything.** You attest to the
facts, fixed rules pick the legal route, and the agent researches who to
contact.

> Hackathon project, in progress. Sections marked *planned* aren't built yet.

## How it works

1. **Enrol:** add a few photos of your face and any original photos you own.
2. **Find:** search and crawl for pages showing your face or copies of your
   photos.
3. **Decide:** answer a few questions per appearance. Fixed rules pick the
   route: copyright notice, impersonation report, intimate-image report,
   privacy request, leave alone, or hold for review.
4. **Send:** a Strands agent finds the recipient (site, then host, then search
   engine). The request comes from a fixed template, and you approve each one.
5. **Verify:** re-check the page later and escalate if nothing changed.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, oxlint |
| API | Python 3.12, FastAPI, uvicorn (*planned*) |
| Agent | Strands Agents SDK on Akamai hosted inference (*planned*) |
| Face matching | OpenCV YuNet + SFace, run locally (*planned*) |
| Copy detection | Perceptual hash, then SIFT + RANSAC (*planned*) |
| Crawl / evidence | httpx + Playwright (*planned*) |
| Data | SQLite + SQLAlchemy (*planned*) |
| Storage | Akamai Object Storage (*planned*) |
| Hosting | One Akamai (Linode) instance; FastAPI serves the built frontend (*planned*) |

## Design

- **Mood:** CCTV footage, the feeling of being watched.
  - The landing page is a dimmed, grayscale wall of faces.
  - Cells occasionally light up as a match or a flag, or dissolve into dust.
- **Palette:** black, white, and one purple accent.
- **Type:** Geist Pixel Square and Geist Mono (SIL Open Font License), bundled
  locally.
- **Details:**
  - The nav logo is a purple snake eye whose pupil follows your cursor.
  - "About" is a camera viewfinder over a blurred feed, with corner
    brackets, a blinking REC light, a live clock and a running timecode.
  - Its copy types itself out in a monospace font.
- **Restraint:** motion is ambient and sparse. It should make the site feel
  alive without getting in the way of the task.
- **Built for usability:** the rules come from Ant Design, Material 3, and IBM
  Carbon.
  - Status is never shown by color alone.
  - Everything works by keyboard.
  - Reduced-motion settings are respected.
  - Every send needs explicit approval.
- **Light dependencies:** no UI component library. The animated grid is plain
  DOM plus one shared canvas for the dust effect.

## Privacy commitments

- Face matching runs locally.
- Face photos are never sent to the language model; it sees page text and URLs
  only.
- Nothing is submitted to real sites. Real-site results stop at a drafted
  request and a named recipient.

## Run the frontend

```sh
cd frontend
npm install
npm run dev     # http://localhost:5173
npm run build   # type-check and build to frontend/dist
npm run lint
```
