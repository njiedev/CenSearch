const steps = [
  { title: 'Start with you', text: 'Add your photos. Matching stays on our server; your face never goes to the AI model.', kind: 'enroll' },
  { title: 'Find your matches', text: 'Find pages showing your face or copies of the photos you own.', kind: 'find' },
  { title: 'Review and request', text: 'Select your matches and accept the legal warning. The agent picks a route and prepares the request.', kind: 'request' },
  { title: 'Follow it through', text: 'We check again, read replies, and show what changed. A reasoned refusal goes to review.', kind: 'verify' },
]

function StepPreview({ kind }: { kind: string }) {
  if (kind === 'enroll') {
    return <div className="step-portrait"><div className="portrait-frame"><svg viewBox="0 0 100 120" fill="none" aria-hidden="true"><circle cx="50" cy="40" r="19" /><path d="M15 109v-9a35 35 0 0 1 70 0v9" /></svg><span className="scan-line" /></div><span className="preview-chip">＋ Add your photos</span></div>
  }
  if (kind === 'find') {
    return <div className="match-orbit"><span className="orbit-center">Your photos</span><span className="orbit-node node-one">Profiles</span><span className="orbit-node node-two">Reposts</span><span className="orbit-node node-three">Galleries</span><span className="orbit-node node-four">Copies</span></div>
  }
  if (kind === 'request') {
    return <div className="preview-window"><div className="window-bar"><i /><i /><i /></div><span className="preview-label">Request review</span><div className="preview-row">Match evidence <span>✓</span></div><div className="preview-row">Removal route <span>✓</span></div><div className="preview-row">Recipient <span>✓</span></div><div className="preview-paper"><span /><span /><span /></div><span className="preview-chip">Ready for your approval</span></div>
  }
  return <div className="preview-timeline"><div><i />Request prepared<small>Evidence saved</small></div><div><i />Check the page<small>Look for a change</small></div><div><i />Show the outcome<small>Removed, pending, or review</small></div></div>
}

export default function Features() {
  return (
    <section className="features landing-section" id="features" aria-labelledby="features-title">
      <div className="section-inner">
        <h2 id="features-title">Your face. Your next move.</h2>
        <p className="section-sub">From the first photo to the follow-up.<br />One place to see where things stand.</p>
        <div className="how-grid">
          {steps.map(({ title, text, kind }) => (
            <article className="how-card" key={kind}>
              <div className="step-preview" aria-hidden="true"><StepPreview kind={kind} /></div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
        <p className="demo-note">Illustrative workflow. Automatic email requires a connected sending account and your batch authorization. Website forms require manual submission.</p>
      </div>
    </section>
  )
}
