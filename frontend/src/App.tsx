import Nav from './Nav'
import Features from './Features'
import Faq from './Faq'
import Footer from './Footer'
import Mission from './Mission'
import PhotoGrid from './PhotoGrid'

export default function App() {
  return (
    <div className="landing">
      <PhotoGrid framed />
      <Nav />
      <main>
        <section className="hero" id="top">
          <div className="hero-copy">
            <h1 className="hero-headline">
              Your <span className="pixel-word">face</span> is out there.
              <br />
              We take it <span className="pixel-word">down</span>.
            </h1>
            <p className="hero-sub">
              We search the web for your face and send deletion requests wherever they're needed.
            </p>
            <div className="hero-actions">
              <a className="landing-button" href="/signup.html">
                Start here
              </a>
              <a className="landing-link" href="/app/?sample=1">
                Try the demo
              </a>
            </div>
          </div>
        </section>
        <Mission />
        <Features />
        <Faq />
      </main>
      <Footer />
    </div>
  )
}
