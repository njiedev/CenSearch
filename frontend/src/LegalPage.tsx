import Footer from './Footer'
import Nav from './Nav'
import { CONTACT_EMAIL, type LegalDocument } from './legal'

export default function LegalPage({ document }: { document: LegalDocument }) {
  const contents = document.sections.map((section, index) => (
    <a key={section.id} href={`#${section.id}`}>{index + 1}. {section.title}</a>
  ))

  return (
    <div className="landing document-page">
      <Nav onLanding={false} />
      <main className="document-main" id="top">
        <header className="document-heading">
          <h1>{document.title}</h1>
          <p>Last updated <time dateTime="2026-10-10">October 10, 2026</time></p>
        </header>
        <div className="document-layout">
          <nav className="document-contents" aria-label="On this page">
            <h2>On this page</h2>
            {contents}
          </nav>
          <details className="document-contents-compact">
            <summary>On this page</summary>
            <nav aria-label="On this page">{contents}</nav>
          </details>
          <article className="document-body">
            <p className="document-intro">{document.introduction}</p>
            {document.sections.map((section, index) => (
              <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}>
                <h2 id={`${section.id}-title`}>{index + 1}. {section.title}</h2>
                {section.paragraphs.map(paragraph => <p key={paragraph}>{paragraph}</p>)}
              </section>
            ))}
            <a className="text-link" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </article>
        </div>
      </main>
      <Footer />
    </div>
  )
}
