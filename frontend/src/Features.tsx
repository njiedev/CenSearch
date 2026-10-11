import enrollment from './assets/product/enrollment.png'
import matches from './assets/product/matches.png'
import requestReview from './assets/product/request-review.png'
import followUp from './assets/product/follow-up.png'

const steps = [
  { title: 'Start with you', text: 'Add your photos. Matching stays on our server; your face never goes to the AI model.', kind: 'enroll', image: enrollment, alt: 'CenSearch enrollment form with face and original photo uploads' },
  { title: 'Find your matches', text: 'Find pages showing your face or copies of the photos you own.', kind: 'find', image: matches, alt: 'CenSearch match grid showing selectable demo results' },
  { title: 'Review and request', text: 'Select your matches and accept the legal warning. The agent picks a route and prepares the request.', kind: 'request', image: requestReview, alt: 'CenSearch request review with recipient evidence and the exact notice' },
  { title: 'Follow it through', text: 'We check again, read replies, and show what changed. A reasoned refusal goes to review.', kind: 'verify', image: followUp, alt: 'CenSearch follow-up panel showing a verified removal from a local test site' },
]

export default function Features() {
  return (
    <section className="features landing-section" id="features" aria-labelledby="features-title">
      <div className="section-inner">
        <h2 id="features-title">Your face. Your next move.</h2>
        <p className="section-sub">From the first photo to the follow-up.<br />One place to see where things stand.</p>
        <div className="how-grid">
          {steps.map(({ title, text, kind, image, alt }) => (
            <article className="how-card" key={kind}>
              <div className={`step-preview step-preview--${kind}`}><img src={image} alt={alt} width={kind === 'enroll' ? 840 : 1200} height={1480} loading="lazy" decoding="async" draggable={false} /></div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
        <p className="demo-note">Screenshots from CenSearch using demo data and a local test-site removal. Automatic email requires a connected sending account and your batch authorization. Website forms require manual submission.</p>
      </div>
    </section>
  )
}
