import { useState, type FormEvent } from 'react'
import Footer from './Footer'
import Nav from './Nav'
import { CONTACT_EMAIL } from './legal'

export default function Contact() {
  const [prepared, setPrepared] = useState(false)

  function prepareEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const subject = `CenSearch — ${fields.get('topic')}`
    const body = `${fields.get('message')}\n\n${fields.get('name')}\nReply to: ${fields.get('email')}`
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    setPrepared(true)
  }

  return (
    <div className="landing document-page">
      <Nav onLanding={false} />
      <main className="contact-main" id="top">
        <header className="document-heading">
          <h1>Get in touch.</h1>
          <p>Questions, feedback, or something not working?<br />We’re here to help.</p>
          <a className="text-link" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </header>
        <form className="contact-form" onSubmit={prepareEmail} onChange={() => setPrepared(false)}>
          <div className="contact-field">
            <label htmlFor="contact-name">Full name</label>
            <input id="contact-name" name="name" autoComplete="name" placeholder="Your name" maxLength={120} required />
          </div>
          <div className="contact-field">
            <label htmlFor="contact-email">Email</label>
            <input id="contact-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" maxLength={254} required />
          </div>
          <div className="contact-field">
            <label htmlFor="contact-topic">Topic</label>
            <select id="contact-topic" name="topic" defaultValue="" required>
              <option value="" disabled>Select a topic</option>
              <option>General question</option>
              <option>Feedback or a bug</option>
              <option>Privacy or data deletion</option>
              <option>A removal request</option>
            </select>
          </div>
          <div className="contact-field">
            <label htmlFor="contact-message">Message</label>
            <textarea id="contact-message" name="message" placeholder="How can we help?" rows={4} maxLength={1500} aria-describedby="contact-note" required />
          </div>
          <p className="contact-note" id="contact-note">Please don’t include face photos, identification documents or intimate images.</p>
          <div className="contact-action">
            <button className="contact-submit" type="submit">Open email draft <span aria-hidden="true">↗</span></button>
            <p>You review and send it from your email app.</p>
          </div>
          {prepared && <p className="contact-status" role="status">Finish sending in your email app. If it didn’t open, email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> directly. Nothing has been sent by this website.</p>}
          <p className="contact-note">Read our <a href="/legal/privacy-policy/">Privacy Policy</a> for how we handle your message.</p>
        </form>
      </main>
      <Footer />
    </div>
  )
}
