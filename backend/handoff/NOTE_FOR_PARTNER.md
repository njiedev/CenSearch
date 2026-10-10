# For the frontend teammate

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
