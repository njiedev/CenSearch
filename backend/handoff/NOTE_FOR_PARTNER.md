# For the frontend teammate

The product changed on 2026-10-10: the person no longer answers questions per match. They select matches,
accept one legal-responsibility warning, and the agent picks the route, finds the recipient, drafts and sends.

Give your coding agent FRONTEND_AGENT_BRIEF.md and openapi.json from this folder.
The brief was written before this change: it covers enroll, find and the older per-case screens, but not batches.
For the batch flow use openapi.json and copy backend/demo-ui/src/Matches.tsx, which is the working screen.

The batch flow in three calls:

1. GET /api/cases lists matches. Each has matched_image_url, possible_action and batch_outcome.
2. GET /api/batches/warning returns the warning text. Show it exactly and require acceptance.
3. POST /api/batches with case_ids, contact, accepted_by and accepted_warning=true, then poll
   GET /api/batches/{batch_id} until completed equals total.

Each batch item moves through reviewing, capturing, researching, drafting and sending, and ends as sent,
drafted_not_sent, left_alone, held_for_review or failed. Show the route, the reason, the recipient and the
exact notice for every item afterwards; nothing the agent did may be hidden.

Real websites always end as drafted_not_sent with a named recipient; the person sends those themselves.
Only our local test sites receive automatic requests. A batch never resends a case that already has a notice.
A reasoned refusal stops escalation. Search delisting is shown separately from removal of the original image.

The older per-case endpoints (answers, approve, send, verify) still work and the demo console keeps those screens.

There is no model key yet, so the route and the recipient research both come from a clearly labelled
rule-based fallback, not the agent. The application sends only text and URLs to the model, never photos.

Your frontend and port 5173 were left alone. The backend normally uses 8190, with the test console served
from that same address. The separate console development server uses 5183.

The last build round reported 125 tests and the local browser scenarios passing. This is not a cloud
deployment or a real-face search demo. Cloud scripts are ready for owner review but have not been run.
Use approved owner photos for the real demo; the development research pictures must stay local.
