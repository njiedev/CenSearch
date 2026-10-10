# AGENTS.md: CenSearch frontend

Read the root `AGENTS.md` first. It explains what the product is, how the
end-to-end loop works (enroll → find → decide → send → verify), and the full
backend and frontend stack. This file covers the frontend only. Most of the
work happens here, in `frontend/`, on the `frontend` branch.

## Who and what

- The owner of this folder is the frontend developer on a hackathon team.
- The project is **CenSearch**. The root brief still calls it "Likeness Guard";
  CenSearch wins for anything user-facing.
- Our goal is to **win Best Design**, and the root brief's goals still apply:
  the sponsor tracks and a demo a judge can follow in under 3 minutes.
- Use the product loop in the root `AGENTS.md` to plan the screens and the
  flow between them.

## The vibe

- **CCTV footage, being watched.** The site should feel alive and watchful,
  never cheesy.
- **The landing page backdrop sets the tone.** It's a grayscale grid of faces,
  dimmed, with a vignette. Occasional cells light up as a match or a flag, or
  dissolve into dust (`src/PhotoGrid.tsx`, `src/dust.ts`). New screens should
  feel like they belong to the same world.
- **Clean over clever.** No heavy, distracting animation. Motion should be
  slow, sparse, and ambient, like a monitor quietly scanning. It should never
  compete with the task on screen.
- **Palette: black, white, and purple** (fairly confident, not final).
  - Black and near-black for surfaces.
  - White and grays for text.
  - Purple as the single brand accent.
  - The landing grid currently uses green for matches and red for flags. Expect
    those to move toward the palette, but keep status colors semantic (see
    Status indicators below). Purple is the brand color, not a status.
- **Inspiration:** Overmind is the current favorite reference. The owner will
  share more sites as we go. Note each one here with what we're borrowing from
  it.
- **We're in rough drafts.** Expect direction to change. Prefer changes that
  are easy to throw away over heavy abstractions.

## Working rules

- **Branch:** work on `frontend`. Don't commit to `main`.
- **Commit early and often, in the Stripe style.**
  - Messages are short, imperative, and sentence case, with no prefix or
    trailing period. Examples: `Add enroll screen`, `Fix grid resize on mobile`.
  - One logical change per commit.
  - End commit messages with the attribution trailer.
- **README:** keep the root `README.md` current with anything a hackathon
  judge would want to know: stack, design decisions, how to run it, and what's
  real versus mocked.
- **Stack:** React 19, Vite, and TypeScript, linted with oxlint. The build is
  static files that FastAPI serves, so there's no separate frontend host.
- **Before calling a change done:** run `npm run build` and `npm run lint`,
  and look at it in a browser.
- **Leave no dev server running** at the end of a round.

## UX references

Use these three design systems as the reference. We don't import their
component libraries; we borrow their rules.

- **Ant Design** (ant.design/docs/spec): feedback, data display, and
  restraint. Good for dense, task-focused screens.
- **Material 3** (m3.material.io): interaction states, touch targets, spacing
  grid, and responsive breakpoints.
- **IBM Carbon** (carbondesignsystem.com): accessibility, status indicators,
  empty states, and loading patterns.

When they disagree, follow the stricter rule. The surveillance mood is a
visual layer on top of these rules and never an excuse to break them. The
screens should feel watched, but stay readable and usable.

## Rules for this product

This app handles people's faces and walks them through legal-adjacent
decisions. Behind the surveillance aesthetic, the UI has to feel calm, honest,
and in the user's control.

- **Never imply the agent attested to anything.** Visually separate what the
  person said, what the rules decided, and what the agent found. Label each
  one.
- **Every send needs explicit approval of that specific request.** Show the
  recipient and the full drafted text before the confirm button. No bulk
  "send all".
- **Say when something is mock, faked, or simulated.** Examples: mock sites,
  the advanced clock, drafts that won't be submitted to real sites. Use a
  visible label, not just a tooltip.
- **Treat face photos as sensitive.** Don't put them in URLs, logs, or
  third-party embeds. Make it clear where a photo is going before upload.
- **A judge must follow the demo in under 3 minutes.** One primary action per
  screen, an obvious next step, and no dead ends.

## Layout and spacing

- Use a 4px base grid with 8px steps for spacing (M3). No arbitrary values
  like 13px.
- Group related items close together and separate unrelated ones with more
  space (Ant: proximity).
- Align to a shared edge and left-align blocks of text (Ant: alignment).
- Give the same thing the same look on every screen (Ant: repetition).
- Order content by importance and how often people act on it.
- Check widths of 360px, 600px, 840px, and 1200px or more (M3 compact,
  medium, expanded, and large). Mobile is out of scope, but nothing should
  break or scroll sideways at narrow widths.

## Interaction states

- Every interactive element needs hover, focus-visible, pressed, and disabled
  states (M3).
- Show a state as a tinted overlay on the element, not a layout shift. M3
  uses about 8% opacity for hover and about 10% for focus and pressed.
- Disabled content is about 38% opacity. Explain why something is disabled
  when it isn't obvious.
- Make touch and click targets at least 48×48px, or pad the hit area to that
  size (M3).
- Keep focus rings visible. Never `outline: none` without a replacement.

## Feedback, loading, and errors

- **Respond right away** to every action (Ant: react immediately).
- **Under ~1s:** no indicator needed.
- **Under a few seconds:** inline loading on the triggering control (Carbon).
- **Longer, or multi-step** (crawling, matching, agent lookup): a progress
  indicator with stage text such as "Fetching contact page…", plus a cancel
  option (Ant, Carbon). Scanning is a natural place for the surveillance
  aesthetic.
- **Initial page or list load:** skeletons for containers and data like
  cards, tables, and lists. Never use skeletons for buttons, inputs, or modals
  (Carbon).
- **Success** for minor actions: a brief, non-blocking message that
  auto-dismisses after about 3s (Ant).
- **Important failures:** stay on screen and explain what happened and what
  to do next. Never show only a toast that disappears (Ant).
- **Form errors:** inline next to the field, with a specific message, and
  kept until the field is edited (Ant).
- **Destructive or irreversible actions:** confirm near the trigger and name
  the consequence. Sending a request counts as irreversible.
- Don't over-notify. Skip feedback when the result is already visible.

## Status indicators (Carbon)

- Never use color alone. Pair color with an icon or shape and a text label,
  and make sure it still reads in grayscale.
- Color meanings:
  - red: error or danger
  - orange: serious warning
  - yellow: warning
  - green: success
  - blue: in progress or info
  - gray: not started or draft
- Keep purple out of status meanings so the brand accent never reads as a
  status.
- Keep to five or six distinct statuses per view. A group shows its
  highest-severity status.
- Request lifecycle states (drafted, sent, acted, refused, escalated, held for
  review) need consistent names, icons, and colors on every screen.

## Empty states (Carbon)

- Plan for three kinds: no data yet, no results after an action, and error or
  permission problems.
- Include a short title, one sentence on the next step, and one primary
  action. No dead ends and no jokes.
- Replace the whole component (for example, the table) rather than rendering
  an empty frame.
- In tables, show `-` for a missing value (Ant).

## Content and copy

- Use plain language and no jargon. Explain legal routes in one sentence a
  non-lawyer understands.
- Buttons are verbs that name the outcome, like "Send request" or "Draft
  notice". Avoid "OK" and "Submit".
- Show match confidence in human terms with the evidence behind it, not a raw
  score alone.
- Keep timestamps, statuses, and actions in tables on one line, and truncate
  long text with a way to see all of it (Ant).

## Accessibility (Carbon, WCAG 2.1 AA)

- Text contrast must be at least 4.5:1, or 3:1 for large text and UI
  components or indicators. Watch purple on black closely; many purples fail
  it.
- Everything must work by keyboard alone, in a logical tab order. Modals trap
  focus and give it back when they close.
- Use semantic HTML first: `button` for actions, `a` for navigation, and real
  `label`s on inputs.
- Meaningful images need alt text. Decorative ones use `alt=""`. Face
  thumbnails need neutral alt text that doesn't name the person unless they
  enrolled.
- Announce loading, success, and failure with `aria-live` regions.
- Respect `prefers-reduced-motion`. That includes the animated photo grid and
  the dust effect. No autoplaying flashing content.

## Motion

- Use motion to explain a change: where something came from or went (Ant: use
  transition). Ambient "being watched" motion is fine in the background, but
  keep it out of the way on task screens.
- Keep UI transitions short, about 150–300ms. Never block input waiting for
  an animation to finish.

## Testing checklist for frontend changes

Run through this before calling a frontend change done:

1. Run the real app in a browser. A passing type check isn't enough.
2. Click the happy path end to end, then try at least one failure path.
3. Check the loading, empty, error, and success states for each view you
   touched.
4. Tab through with the keyboard only. Is focus always visible and is the
   order sensible?
5. Resize to 360px and 1440px wide and check that nothing overlaps or
   overflows.
6. Turn on reduced motion and confirm the animations calm down.
7. Paste in very long text, such as a long URL or page title, and check that
   it truncates cleanly.
8. Make sure nothing implies the app sent something it didn't, or that the
   agent vouched for a fact.
9. Report what you actually checked and what you skipped.
